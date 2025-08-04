// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";

contract BLSVerify {
    function G1_GEN() public pure returns (BLS.G1Point memory) {
        return BLS.G1Point(
            bytes32(uint256(31827880280837800241567138048534752271)),
            bytes32(uint256(88385725958748408079899006800036250932223001591707578097800747617502997169851)),
            bytes32(uint256(11568204302792691131076548377920244452)),
            bytes32(uint256(114417265404584670498511149331300188430316142484413708742216858159411894806497))
        );
    }

    function NEG_G1_GEN() public pure returns (BLS.G1Point memory) {
        return BLS.G1Point(
            bytes32(uint256(31827880280837800241567138048534752271)),
            bytes32(uint256(88385725958748408079899006800036250932223001591707578097800747617502997169851)),
            bytes32(uint256(22997279242622214937712647648895181298)),
            bytes32(uint256(46816884707101390882112958134453447585552332943769894357249934112654335001290))
        );
    }

    function verify(bytes memory message, BLS.G2Point memory sig, BLS.G1Point memory pubKey)
        public
        view
        returns (bool)
    {
        BLS.G2Point memory hmsg = BLS.hashToG2(message);

        BLS.G1Point[] memory g1points = new BLS.G1Point[](2);
        BLS.G2Point[] memory g2points = new BLS.G2Point[](2);

        g1points[0] = NEG_G1_GEN();
        g1points[1] = pubKey;
        g2points[0] = sig;
        g2points[1] = hmsg;

        return BLS.pairing(g1points, g2points);
    }

    function verifyAgg(bytes[] memory msgs, BLS.G1Point[] memory pubKeys, BLS.G2Point memory aggSig)
        public
        view
        returns (bool)
    {
        BLS.G1Point[] memory g1Points = new BLS.G1Point[](msgs.length + 1);
        BLS.G2Point[] memory g2Points = new BLS.G2Point[](msgs.length + 1);

        for (uint256 i = 0; i < msgs.length; i++) {
            g1Points[i] = pubKeys[i];
            g2Points[i] = BLS.hashToG2(msgs[i]);
        }

        g1Points[msgs.length] = NEG_G1_GEN();
        g2Points[msgs.length] = aggSig;

        return BLS.pairing(g1Points, g2Points);
    }
}
