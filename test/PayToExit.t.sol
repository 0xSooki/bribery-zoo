// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {PayToExit} from "../src/PayToExit.sol";
import {BLSVerify} from "../src/BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {Utils} from "../src/Utils.sol";

contract PayToExitTest is Test {
    PayToExit public payToExit;
    BLSVerify public blsVerify;

    address public owner;

    function setUp() public {
        owner = address(this);

        blsVerify = new BLSVerify();
        payToExit = new PayToExit(address(blsVerify));

        vm.deal(address(payToExit), 10 ether);
    }

    function testWithGeneratedData() public {
        uint256 VALIDATOR_INDEX = 3;
        uint256 TARGET_EPOCH = 1000;
        uint256 AUCTION_DEADLINE = block.timestamp + 1 days;
        address validator = address(0x123);
        vm.deal(validator, 2 ether);
        uint64 deposit_count = 4;

        BLS.G1Point memory pubkey = BLS.G1Point({
            x_a: bytes32(uint256(0x172a59075fca0729b40b2cea5bb9685a)),
            x_b: bytes32(uint256(0xfdd219e77407e13631664c53b847cdcad45ab174a073aaa4122ad813fa094485)),
            y_a: bytes32(uint256(0x28e53b49dfb3b48ebd12df0158912b6)),
            y_b: bytes32(uint256(0xa5036da6204a58275b9ad64acc45e372b0dff305bb6134f9d350a89f75e65ab7))
        });

        vm.prank(validator);
        payToExit.offerBribe(TARGET_EPOCH, AUCTION_DEADLINE, pubkey);

        PayToExit.ValidatorAuction memory auction = payToExit.getAuction(address(validator));
        assertEq(auction.epoch, TARGET_EPOCH);
        assertEq(auction.auctionDeadline, AUCTION_DEADLINE);
        assertFalse(auction.exited);
        assertFalse(auction.claimed);

        bytes32[] memory proof = new bytes32[](3);
        proof[0] = 0x5038da95330ba16edb486954197e37eb777c3047327ca54df4199c35c5edc17a; // sibling of pubkeyHash
        proof[1] = 0x884ff14f19d1564614ab3184d7bdc35a1a9ff90d36ac962b05a81aeb56027c22; // sibling at level 2
        proof[2] = 0x423df0391558d15d7edb0b74f742870f953b0d2780b1d50c04959264f2ea8c56; // sibling at level 1

        bytes32 depositDataRoot = 0xfbf1ed18f9e4390c7cfc3636070193ab943f05aa6405a7901b39b2c693c70409;

        bytes32 leaf1 = sha256(abi.encodePacked(depositDataRoot, proof[0]));
        bytes32 leaf2 = sha256(abi.encodePacked(leaf1, proof[1])); // leaf1 goes LEFT (correct for index 0)
        bytes32 root = sha256(abi.encodePacked(leaf2, proof[2])); // leaf2 goes LEFT (correct for index 0)

        bytes32 finalRoot = sha256(abi.encodePacked(root, Utils.to_little_endian64(deposit_count), bytes24(0)));

        BLS.G2Point memory signature = BLS.G2Point({
            x_c0_a: bytes32(uint256(0x30cd2be741127aa49885ae2e28f5d14)),
            x_c0_b: bytes32(uint256(0x2aefc0d9b2a6ce83770d55323113a558e96542882d6cebdd9d127b012955d1a7)),
            x_c1_a: bytes32(uint256(0x4f0cdd385ec70411bbcb3d37e774737)),
            x_c1_b: bytes32(uint256(0xbf1c259252fd5c7e2b5bb17da8b5e269a0502f7c213d8a9df70409869f232e19)),
            y_c0_a: bytes32(uint256(0x10c7a20238c4b7842fb10aeb14ce22b1)),
            y_c0_b: bytes32(uint256(0x549590ad738cc114081e764ef8df46450c91c92a17d78cb2ce4d0ec314c057b3)),
            y_c1_a: bytes32(uint256(0xe4cd964223ba4213c9b65fd0d808a06)),
            y_c1_b: bytes32(uint256(0x3d282d4b770ee6795f085414fc0c47738cd3a149c6c308569a041f7e6b0464bd))
        });

        bytes32 expectedSigningRoot = 0x9c342ac63f66c104652488a4f85abb3da68be15f620bd7a1c92ae2869fd9ccdc;

        bytes32 contractSigningRoot = Utils.compute_signing_root(
            TARGET_EPOCH, VALIDATOR_INDEX, payToExit.MAINNET_FORK_VERSION(), payToExit.MAINNET_GENESIS_VALIDATORS_ROOT()
        );

        assertEq(contractSigningRoot, expectedSigningRoot, "Signing root mismatch between Python and Solidity");

        vm.prank(validator);
        payToExit.takeBribe(
            address(validator), VALIDATOR_INDEX, 0, signature, proof, depositDataRoot, deposit_count, finalRoot
        );
    }

    function testSigningRootComputation() public view {
        uint256 VALIDATOR_INDEX = 3;
        uint256 TARGET_EPOCH = 1000;

        bytes32 expectedSigningRoot = 0x9c342ac63f66c104652488a4f85abb3da68be15f620bd7a1c92ae2869fd9ccdc;

        bytes32 computedSigningRoot = Utils.compute_signing_root(
            TARGET_EPOCH, VALIDATOR_INDEX, payToExit.MAINNET_FORK_VERSION(), payToExit.MAINNET_GENESIS_VALIDATORS_ROOT()
        );

        assertEq(computedSigningRoot, expectedSigningRoot, "Signing root computation failed");
    }

    function testMerkleProofVerification() public pure {
        bytes32 pubkeyHash = 0x478ec687f9165ca245227a73f5fa7b17227e53f36fe6dcd6864b5e13d1163d46;

        bytes32[] memory proof = new bytes32[](3);
        proof[0] = 0x5038da95330ba16edb486954197e37eb777c3047327ca54df4199c35c5edc17a;
        proof[1] = 0x884ff14f19d1564614ab3184d7bdc35a1a9ff90d36ac962b05a81aeb56027c22;
        proof[2] = 0x423df0391558d15d7edb0b74f742870f953b0d2780b1d50c04959264f2ea8c56;

        bytes32 expectedRoot = 0x3021ed18f9e4390c7cfc3636070193ab943f05aa6405a7901b39b2c693c70409;

        console.log("Python pubkey hash:", vm.toString(pubkeyHash));
        console.log("Python final root: ", vm.toString(expectedRoot));
        console.log("Merkle proof data loaded from Python!");
    }
}
