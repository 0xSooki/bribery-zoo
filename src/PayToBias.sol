// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {HeaderVerify} from "./HeaderVerify.sol";

contract PayToBias {
    struct ValidatorAuction {
        address validator;
        uint256 blockNumber;
        bool withhold;
        bool claimed;
        uint256 auctionDeadline;
        bytes32 blockHash;
    }

    struct Bid {
        address bidder;
        uint256 amount;
        bool publishChoice;
    }

    HeaderVerify public immutable headerVerify;
    address public owner;
    uint256 public constant BLOCK_TIME = 12;

    mapping(uint256 => ValidatorAuction) public validatorAuctions;
    mapping(uint256 => mapping(bool => uint256)) public totalBids;
    mapping(uint256 => mapping(bool => mapping(address => uint256))) public contributions;
    mapping(address => uint256) public balances;

    // reentrancy guard
    uint256 private _locked = 1;

    modifier nonReentrant() {
        require(_locked == 1, "Reentrancy");
        _locked = 2;
        _;
        _locked = 1;
    }

    // events
    event AuctionCreated(uint256 indexed blockNumber, address indexed validator, uint256 deadline);
    event BidPlaced(
        uint256 indexed blockNumber, address indexed bidder, bool withholdSide, uint256 amount, uint256 newTotal
    );
    event AuctionResolved(uint256 indexed blockNumber, bool withhold, address validator, uint256 paidAmount);
    event RefundClaimed(uint256 indexed blockNumber, bool withholdSide, address indexed bidder, uint256 amount);
    event Withdraw(address indexed account, uint256 amount);

    constructor(address headerVerifyAddress) {
        owner = msg.sender;
        headerVerify = HeaderVerify(headerVerifyAddress);
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not the owner");
        _;
    }

    /**
     * @notice Create an auction for a specific block number
     * @param blockNumber The block number the validator is supposed to propose
     * @param auctionDeadline When the auction ends
     */
    function createAuction(uint256 blockNumber, uint256 auctionDeadline) external {
        require(validatorAuctions[blockNumber].validator == address(0), "Auction already exists");
        require(auctionDeadline > block.timestamp, "Auction deadline must be in future");
        require(blockNumber > block.number, "Block must be in the future");
        validatorAuctions[blockNumber] = ValidatorAuction({
            validator: msg.sender,
            blockNumber: blockNumber,
            withhold: false,
            claimed: false,
            auctionDeadline: auctionDeadline,
            blockHash: bytes32(0)
        });
        emit AuctionCreated(blockNumber, msg.sender, auctionDeadline);
    }

    /**
     * @notice Place a bid to influence outcome (true = pay to withhold, false = pay to publish)
     * @param blockNumber The block number to bid on
     * @param withholdSide Set true to fund withhold incentive, false to fund publish incentive
     */
    function placeBid(uint256 blockNumber, bool withholdSide) external payable {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(auction.validator != address(0), "Auction does not exist");
        require(block.timestamp < auction.auctionDeadline, "Auction has ended");
        require(msg.value > 0, "Bid must be greater than 0");
        contributions[blockNumber][withholdSide][msg.sender] += msg.value;
        totalBids[blockNumber][withholdSide] += msg.value;
        emit BidPlaced(blockNumber, msg.sender, withholdSide, msg.value, totalBids[blockNumber][withholdSide]);
    }

    /**
     * @notice Submit proof whether validator withheld or published their block
     */
    function takeBribe(
        uint256 blockNumber,
        HeaderVerify.BlockHeader memory parentHeader,
        HeaderVerify.BlockHeader memory nextHeader
    ) external virtual nonReentrant {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(auction.validator != address(0), "Auction does not exist");
        require(parentHeader.number == blockNumber - 1, "Invalid parent block number");
        require(nextHeader.number == blockNumber, "Invalid next block number");
        bytes32 parentHash = _getBlockHash(blockNumber - 1);
        bytes32 nextHash = _getBlockHash(blockNumber);
        require(parentHash != bytes32(0), "Parent block hash not available");
        require(nextHash != bytes32(0), "Next block hash not available");
        require(headerVerify.verifyBlockHash(parentHeader, parentHash), "Invalid parent block header or hash");
        require(headerVerify.verifyBlockHash(nextHeader, nextHash), "Invalid next block header or hash");
        require(
            nextHeader.parentHash == parentHash,
            "Next block should point to parent, proving validator block was skipped"
        );
        uint256 timeGap = nextHeader.timestamp - parentHeader.timestamp;
        auction.withhold = timeGap > BLOCK_TIME + 4;
        _resolveAuction(blockNumber);
    }

    /**
     * @dev Internal hook to fetch block hash, overridden in testable subclass for mocking.
     */
    function _getBlockHash(uint256 n) internal view virtual returns (bytes32) {
        return blockhash(n);
    }

    function _resolveAuction(uint256 blockNumber) internal virtual {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(
            auction.withhold || (auction.auctionDeadline < block.timestamp),
            "Block was either not witheld or not yet over deadline"
        );
        uint256 winningTotal = totalBids[blockNumber][auction.withhold];
        if (winningTotal > 0) {
            (bool ok,) = auction.validator.call{value: winningTotal}("");
            require(ok, "Transfer failed");
        }
        auction.claimed = true;
        emit AuctionResolved(blockNumber, auction.withhold, auction.validator, winningTotal);
    }

    /**
     * @notice Deposit funds to contract
     */
    function depositFunds() external payable {
        balances[msg.sender] += msg.value;
    }

    /**
     * @notice Withdraw funds from contract
     */
    function withdrawFunds() external nonReentrant {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");
        balances[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
        emit Withdraw(msg.sender, amount);
    }

    /**
     * @notice Get auction details for a block number
     */
    function getAuction(uint256 blockNumber) external view returns (ValidatorAuction memory) {
        return validatorAuctions[blockNumber];
    }

    /**
     * @notice Get highest bids for both choices
     */
    function getTotals(uint256 blockNumber) external view returns (uint256 withholdTotal, uint256 publishTotal) {
        return (totalBids[blockNumber][true], totalBids[blockNumber][false]);
    }

    function contributionOf(uint256 blockNumber, bool withholdSide, address bidder) external view returns (uint256) {
        return contributions[blockNumber][withholdSide][bidder];
    }

    function claimRefund(uint256 blockNumber, bool withholdSide) external nonReentrant {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(auction.claimed, "Not resolved");
        require(auction.withhold != withholdSide, "Winning side");
        uint256 amount = contributions[blockNumber][withholdSide][msg.sender];
        require(amount > 0, "No refund");
        contributions[blockNumber][withholdSide][msg.sender] = 0;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "Refund fail");
        emit RefundClaimed(blockNumber, withholdSide, msg.sender, amount);
    }

    /**
     * @notice Check if auction can be claimed
     */
    function canClaim(uint256 blockNumber) external view returns (bool) {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        return !auction.claimed && (auction.withhold || block.timestamp > auction.auctionDeadline);
    }

    /**
     * @notice Check if auction is still active for bidding
     */
    function isAuctionActive(uint256 blockNumber) external view returns (bool) {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        return block.timestamp <= auction.auctionDeadline;
    }
}
