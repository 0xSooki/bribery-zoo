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
    mapping(uint256 => mapping(bool => Bid)) public highestBids;
    mapping(address => uint256) public balances;

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

        validatorAuctions[blockNumber] = ValidatorAuction({
            validator: msg.sender,
            blockNumber: blockNumber,
            withhold: false,
            claimed: false,
            auctionDeadline: auctionDeadline,
            blockHash: bytes32(0)
        });
    }

    /**
     * @notice Place a bid on whether a validator will publish or withhold their block
     * @param blockNumber The block number to bid on
     * @param publishChoice true = bet on publish, false = bet on withhold
     */
    function placeBid(uint256 blockNumber, bool publishChoice) external payable {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(auction.validator != address(0), "Auction does not exist");
        require(block.timestamp < auction.auctionDeadline, "Auction has ended");
        require(msg.value > 0, "Bid must be greater than 0");

        Bid storage currentHighestBid = highestBids[blockNumber][publishChoice];
        require(msg.value > currentHighestBid.amount, "Bid too low");

        // Refund previous highest bidder
        if (currentHighestBid.bidder != address(0)) {
            balances[currentHighestBid.bidder] += currentHighestBid.amount;
        }

        highestBids[blockNumber][publishChoice] =
            Bid({bidder: msg.sender, amount: msg.value, publishChoice: publishChoice});
    }

    /**
     * @notice Submit proof whether validator withheld or published their block
     */
    function takeBribe(
        uint256 blockNumber,
        HeaderVerify.BlockHeader memory parentHeader,
        HeaderVerify.BlockHeader memory nextHeader
    ) external virtual {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(auction.validator != address(0), "Auction does not exist");
        // require(!auction.withhold, "Block was withhold");
        // require(!auction.claimed, "Already claimed");

        require(parentHeader.number == blockNumber - 1, "Invalid parent block number");
        require(nextHeader.number == blockNumber, "Invalid next block number");

        bytes32 parentHash = blockhash(blockNumber - 1);
        bytes32 nextHash = blockhash(blockNumber);

        require(parentHash != bytes32(0), "Parent block hash not available");
        require(nextHash != bytes32(0), "Next block hash not available");

        require(headerVerify.verifyBlockHash(parentHeader, parentHash), "Invalid parent block header or hash");
        require(headerVerify.verifyBlockHash(nextHeader, nextHash), "Invalid next block header or hash");

        require(
            nextHeader.parentHash == parentHash,
            "Next block should point to parent, proving validator block was skipped"
        );

        uint256 timeGap = nextHeader.timestamp - parentHeader.timestamp;

        if (timeGap > BLOCK_TIME + 4) {
            auction.withhold = true;
        } else {
            auction.withhold = false;
        }

        _resolveAuction(blockNumber);
    }

    function _resolveAuction(uint256 blockNumber) internal virtual {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(
            auction.withhold || (auction.auctionDeadline < block.timestamp),
            "Block was either not witheld or not yet over deadline"
        );

        Bid storage withholdBid = highestBids[blockNumber][true];
        Bid storage publishBid = highestBids[blockNumber][false];

        Bid storage winningBid = auction.withhold ? withholdBid : publishBid;
        Bid storage losingBid = auction.withhold ? publishBid : withholdBid;

        if (winningBid.bidder != address(0)) {
            payable(auction.validator).transfer(winningBid.amount);
            auction.claimed = true;
        }

        if (losingBid.bidder != address(0)) {
            balances[losingBid.bidder] += losingBid.amount;
        }
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
    function withdrawFunds() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");

        balances[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
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
    function getHighestBids(uint256 blockNumber)
        external
        view
        returns (Bid memory publishBid, Bid memory withholdBid)
    {
        return (highestBids[blockNumber][true], highestBids[blockNumber][false]);
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
