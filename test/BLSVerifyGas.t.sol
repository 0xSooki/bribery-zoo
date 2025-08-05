// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {console} from "forge-std/console.sol";

contract BLSVerifyGasTest is Test {
    BLSVerify blsVerify;

    function setUp() public {
        blsVerify = new BLSVerify();
    }

    function testGasCostsDifferentMessage() public view {
        console.log("=== Detailed Gas Cost Analysis ===");
        console.log("Messages, Gas Used, Gas per Message");

        for (uint256 n = 1; n <= 25; n++) {
            BLS.G1Point[] memory pubKeys = new BLS.G1Point[](n);
            BLS.G2Point[] memory sigs = new BLS.G2Point[](n);
            bytes32[] memory privKeys = new bytes32[](n);
            bytes[] memory messages = new bytes[](n);

            for (uint256 i = 0; i < n; i++) {
                messages[i] = bytes.concat("msg_", bytes32(i));
            }

            BLS.G1Point[] memory g1gen = new BLS.G1Point[](1);
            g1gen[0] = blsVerify.G1_GEN();

            for (uint256 i = 0; i < n; i++) {
                privKeys[i] = bytes32(
                    uint256(keccak256(abi.encodePacked("key_", i)))
                );

                bytes32[] memory scalars = new bytes32[](1);
                BLS.G2Point[] memory hm = new BLS.G2Point[](1);
                hm[0] = BLS.hashToG2(messages[i]);

                scalars[0] = privKeys[i];
                sigs[i] = BLS.msm(hm, scalars);
                pubKeys[i] = BLS.msm(g1gen, scalars);
            }

            BLS.G2Point memory aggSig = sigs[0];
            for (uint256 i = 1; i < n; i++) {
                aggSig = BLS.add(aggSig, sigs[i]);
            }

            uint256 gasBefore = gasleft();
            bool result = blsVerify.verifyAgg(messages, pubKeys, aggSig);
            uint256 gasAfter = gasleft();
            uint256 gasUsed = gasBefore - gasAfter;
            uint256 gasPerMessage = gasUsed / n;

            assertTrue(result, "Verification should succeed");
            console.log("%d, %d, %d", n, gasUsed, gasPerMessage);
        }
    }

    function testGasSameMessage() public view {
        console.log("=== Detailed Gas Cost Analysis ===");
        console.log("Messages, Gas Used, Gas per Message");

        for (uint256 n = 1; n <= 25; n++) {
            BLS.G1Point[] memory pubKeys = new BLS.G1Point[](n);
            BLS.G2Point[] memory sigs = new BLS.G2Point[](n);
            bytes32[] memory privKeys = new bytes32[](n);
            bytes memory message = "test";

            BLS.G1Point[] memory g1gen = new BLS.G1Point[](1);
            g1gen[0] = blsVerify.G1_GEN();

            for (uint256 i = 0; i < n; i++) {
                privKeys[i] = bytes32(
                    uint256(keccak256(abi.encodePacked("key_", i)))
                );

                bytes32[] memory scalars = new bytes32[](1);
                BLS.G2Point[] memory hm = new BLS.G2Point[](1);
                hm[0] = BLS.hashToG2(message);

                scalars[0] = privKeys[i];
                sigs[i] = BLS.msm(hm, scalars);
                pubKeys[i] = BLS.msm(g1gen, scalars);
            }

            // Aggregate signatures
            BLS.G2Point memory aggSig = sigs[0];
            for (uint256 i = 1; i < n; i++) {
                aggSig = BLS.add(aggSig, sigs[i]);
            }

            BLS.G1Point memory pubKey = pubKeys[0];
            for (uint256 i = 1; i < n; i++) {
                pubKey = BLS.add(pubKey, pubKeys[i]);
            }

            // Measure gas cost
            uint256 gasBefore = gasleft();
            bool result = blsVerify.verify(message, aggSig, pubKey);
            uint256 gasAfter = gasleft();
            uint256 gasUsed = gasBefore - gasAfter;
            uint256 gasPerMessage = gasUsed / n;

            assertTrue(result, "Verification should succeed");
            console.log("%d, %d, %d", n, gasUsed, gasPerMessage);
        }
    }
}
