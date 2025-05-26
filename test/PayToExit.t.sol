// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {PayToExit} from "../src/PayToExit.sol";
import {BLSVerify} from "../src/BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";

contract PayToExitTest is Test {
    PayToExit public payToExit;

    address public owner;

    uint256 constant INITIAL_BRIBE_AMOUNT = 1 ether;

    function setUp() public {
        owner = address(this);

        payToExit = new PayToExit{value: 10 ether}(INITIAL_BRIBE_AMOUNT);
    }

    function testTakeBribeWithMerkleProof() public {
        uint256 VALIDATOR_INDEX = 3;
        address testValidator = address(0x123);
        vm.deal(testValidator, 0);

        bytes32 privKey = bytes32(uint256(0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef));

        BLS.G1Point memory g1Gen = BLS.G1Point({
            x_a: bytes32(uint256(31827880280837800241567138048534752271)),
            x_b: bytes32(uint256(88385725958748408079899006800036250932223001591707578097800747617502997169851)),
            y_a: bytes32(uint256(11568204302792691131076548377920244452)),
            y_b: bytes32(uint256(114417265404584670498511149331300188430316142484413708742216858159411894806497))
        });

        BLS.G1Point[] memory g1Points = new BLS.G1Point[](1);
        bytes32[] memory scalars = new bytes32[](1);
        g1Points[0] = g1Gen;
        scalars[0] = privKey;

        BLS.G1Point memory pubkey = BLS.msm(g1Points, scalars);

        bytes32 pubkeyHash = sha256(abi.encodePacked(pubkey.x_a, pubkey.x_b, pubkey.y_a, pubkey.y_b));

        bytes32[8] memory leaves = [
            keccak256("leaf0"),
            keccak256("leaf1"),
            keccak256("leaf2"),
            pubkeyHash,
            keccak256("leaf4"),
            keccak256("leaf5"),
            keccak256("leaf6"),
            keccak256("leaf7")
        ];

        bytes32[4] memory level2 = [
            sha256(abi.encodePacked(leaves[0], leaves[1])),
            sha256(abi.encodePacked(leaves[2], leaves[3])),
            sha256(abi.encodePacked(leaves[4], leaves[5])),
            sha256(abi.encodePacked(leaves[6], leaves[7]))
        ];

        bytes32[2] memory level1 =
            [sha256(abi.encodePacked(level2[0], level2[1])), sha256(abi.encodePacked(level2[2], level2[3]))];

        bytes32 merkleRoot = sha256(abi.encodePacked(level1[0], level1[1]));

        bytes32[] memory proof = new bytes32[](3);
        proof[0] = leaves[2];
        proof[1] = level2[0];
        proof[2] = level1[1];

        bytes memory message = abi.encodePacked("exit_validator_", VALIDATOR_INDEX);

        BLS.G2Point[] memory g2Points = new BLS.G2Point[](1);
        g2Points[0] = BLS.hashToG2(message);

        BLS.G2Point memory signature = BLS.msm(g2Points, scalars);

        uint64 deposit_count = 8;
        bytes32 expectedRoot =
            sha256(abi.encodePacked(merkleRoot, payToExit.to_little_endian_64(deposit_count), bytes24(0)));

        uint256 initBalance = address(payToExit).balance;
        uint256 validatorInitBalance = testValidator.balance;
        assertFalse(payToExit.bribeTaken(VALIDATOR_INDEX));

        vm.prank(testValidator);
        payToExit.takeBribe(VALIDATOR_INDEX, pubkey, signature, message, proof, expectedRoot, deposit_count);

        assertTrue(payToExit.bribeTaken(VALIDATOR_INDEX));
        assertEq(address(payToExit).balance, initBalance - INITIAL_BRIBE_AMOUNT);
        assertEq(testValidator.balance, validatorInitBalance + INITIAL_BRIBE_AMOUNT);
    }
}
