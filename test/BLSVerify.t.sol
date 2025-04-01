// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {console} from "forge-std/console.sol";

contract BLSVerifyTest is Test {
    BLSVerify blsVerify;

    function G1_GEN() internal pure returns (BLS.G1Point memory) {
        return BLS.G1Point(
            bytes32(uint256(31827880280837800241567138048534752271)),
            bytes32(uint256(88385725958748408079899006800036250932223001591707578097800747617502997169851)),
            bytes32(uint256(11568204302792691131076548377920244452)),
            bytes32(uint256(114417265404584670498511149331300188430316142484413708742216858159411894806497))
        );
    }

    function NEG_G1_GEN() internal pure returns (BLS.G1Point memory) {
        return BLS.G1Point(
            bytes32(uint256(31827880280837800241567138048534752271)),
            bytes32(uint256(88385725958748408079899006800036250932223001591707578097800747617502997169851)),
            bytes32(uint256(22997279242622214937712647648895181298)),
            bytes32(uint256(46816884707101390882112958134453447585552332943769894357249934112654335001290))
        );
    }

    function setUp() public {
        blsVerify = new BLSVerify();
    }

    function testValidSignature() public {
        bytes32 privKey = bytes32(vm.randomUint());

        BLS.G1Point[] memory g1points = new BLS.G1Point[](1);
        bytes32[] memory scalars = new bytes32[](1);

        scalars[0] = privKey;
        g1points[0] = G1_GEN();

        bytes memory message = "test";
        BLS.G2Point[] memory g2points = new BLS.G2Point[](1);
        g2points[0] = BLS.hashToG2(message);

        BLS.G1Point memory pubKey = BLS.msm(g1points, scalars);
        BLS.G2Point memory sig = BLS.msm(g2points, scalars);

        bool result = blsVerify.verify(message, sig, pubKey);
        assertTrue(result, "Valid signature should pass verification");
    }

    function testValidAggregatedMessages() public {
        uint256 n = 10;

        BLS.G1Point[] memory pubKeys = new BLS.G1Point[](n);
        BLS.G2Point[] memory sigs = new BLS.G2Point[](n);
        bytes32[] memory privKeys = new bytes32[](n);
        bytes[] memory messages = new bytes[](n);

        for (uint256 i = 0; i < n; i++) {
            messages[i] = bytes.concat("test", bytes32(i));
        }

        BLS.G1Point[] memory g1gen = new BLS.G1Point[](1);
        g1gen[0] = G1_GEN();

        for (uint256 i = 0; i < n; i++) {
            privKeys[i] = bytes32(vm.randomUint());

            bytes32[] memory scalars = new bytes32[](1);

            BLS.G2Point[] memory hm = new BLS.G2Point[](1);
            hm[0] = BLS.hashToG2(messages[i]);

            scalars[0] = privKeys[i];
            sigs[i] = BLS.msm(hm, scalars);

            BLS.G1Point[] memory pubKey = new BLS.G1Point[](1);
            pubKeys[i] = BLS.msm(g1gen, scalars);
        }

        BLS.G2Point memory aggSig = sigs[0];
        BLS.G1Point memory aggPubKey = pubKeys[0];

        for (uint256 i = 1; i < n; i++) {
            aggSig = BLS.add(aggSig, sigs[i]);
            aggPubKey = BLS.add(aggPubKey, pubKeys[i]);
        }

        bool result = blsVerify.verifyAgg(messages, pubKeys, aggSig);
        assertTrue(result, "Valid signature should pass verification");
    }

    function testValidAggregatedSigAndPubKey() public {
        uint256 n = 10;

        BLS.G1Point[] memory pubKeys = new BLS.G1Point[](n);
        BLS.G2Point[] memory sigs = new BLS.G2Point[](n);
        bytes32[] memory privKeys = new bytes32[](n);

        BLS.G2Point[] memory hm = new BLS.G2Point[](1);
        bytes memory message = "test";
        hm[0] = BLS.hashToG2(message);

        BLS.G1Point[] memory g1gen = new BLS.G1Point[](1);
        g1gen[0] = G1_GEN();

        for (uint256 i = 0; i < n; i++) {
            privKeys[i] = bytes32(vm.randomUint());

            bytes32[] memory scalars = new bytes32[](1);

            scalars[0] = privKeys[i];
            sigs[i] = BLS.msm(hm, scalars);

            BLS.G1Point[] memory pubKey = new BLS.G1Point[](1);
            pubKeys[i] = BLS.msm(g1gen, scalars);
        }

        BLS.G2Point memory aggSig = sigs[0];
        BLS.G1Point memory aggPubKey = pubKeys[0];

        for (uint256 i = 1; i < n; i++) {
            aggSig = BLS.add(aggSig, sigs[i]);
            aggPubKey = BLS.add(aggPubKey, pubKeys[i]);
        }

        bool result = blsVerify.verify(message, aggSig, aggPubKey);
        assertTrue(result, "Valid signature should pass verification");
    }
}
