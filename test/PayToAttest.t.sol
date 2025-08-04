// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import "../src/PayToAttest.sol";
import "../src/BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";

contract PayToAttestTest is Test {
    PayToAttest public payToAttest;
    BLSVerify public blsVerify;

    address public validator = address(0x123);
    address public bidder1 = address(0x2);
    address public bidder2 = address(0x3);
    address public attacker = address(0x4);

    bytes32 public constant MESSAGE = 0x245968eee740a2658e10f0a3b43e643cde8c70ba2fcff5366dde63195edb603d;
    uint256 public constant SLOT = 3080829;
    bytes32 public constant BEACON_BLOCK_ROOT = 0x4f4250c05956f5c2b87129cf7372f14dd576fc152543bf7042e963196b843fe6;
    uint256 public constant SOURCE_EPOCH = 96274;
    bytes32 public constant SOURCE_ROOT = 0xd24639f2e661bc1adcbe7157280776cf76670fff0fee0691f146ab827f4f1ade;
    uint256 public constant TARGET_EPOCH = 96275;
    bytes32 public constant TARGET_ROOT = 0x9bcd31881817ddeab686f878c8619d664e8bfa4f8948707cba5bc25c8d74915d;
    uint256 public constant BRIBE_AMOUNT = 1 ether;
    uint256 public FUTURE_DEADLINE;

    PayToAttest.AttestationData public attestationData;
    BLS.G1Point public pubKey;
    BLS.G2Point public testSignature;
    bytes32 public privKey;

    function setUp() public {
        blsVerify = new BLSVerify();
        payToAttest = new PayToAttest(address(blsVerify));

        FUTURE_DEADLINE = block.timestamp + 3600; // Set in setUp

        vm.deal(bidder1, 10 ether);
        vm.deal(bidder2, 10 ether);
        vm.deal(validator, 1 ether);
        vm.deal(attacker, 5 ether);

        // Set up test attestation data
        attestationData = PayToAttest.AttestationData({
            slot: SLOT,
            beacon_block_root: BEACON_BLOCK_ROOT,
            source: PayToAttest.Checkpoint({epoch: SOURCE_EPOCH, root: SOURCE_ROOT}),
            target: PayToAttest.Checkpoint({epoch: TARGET_EPOCH, root: TARGET_ROOT})
        });

        privKey = bytes32(vm.randomUint());

        BLS.G1Point[] memory g1points = new BLS.G1Point[](1);
        bytes32[] memory scalars = new bytes32[](1);

        scalars[0] = privKey;
        g1points[0] = blsVerify.G1_GEN();

        pubKey = BLS.msm(g1points, scalars);
    }

    function testOfferAndTakeBribe() public {
        vm.prank(validator);
        payToAttest.offerBribe{value: BRIBE_AMOUNT}(attestationData, pubKey, FUTURE_DEADLINE, MESSAGE, BRIBE_AMOUNT);

        PayToAttest.Auction memory auction = payToAttest.getAuction(MESSAGE);

        BLS.G2Point[] memory g2points = new BLS.G2Point[](1);
        g2points[0] = BLS.hashToG2(abi.encodePacked(auction.m));

        bytes32[] memory scalars = new bytes32[](1);
        scalars[0] = privKey;
        BLS.G2Point memory sig = BLS.msm(g2points, scalars);

        uint256 bribeeBalance = bidder1.balance;

        vm.prank(bidder1);
        payToAttest.takeBribe(MESSAGE, sig);

        bytes32 sigHash = keccak256(abi.encodePacked(sig.x_c0_a, sig.x_c0_b, sig.x_c1_a, sig.x_c1_b));

        assertEq(bidder1.balance, bribeeBalance + BRIBE_AMOUNT);
        assertTrue(payToAttest.claimed(sigHash));
    }

    receive() external payable {}
}
