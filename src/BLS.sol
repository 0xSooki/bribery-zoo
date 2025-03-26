// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

/// @title BLS
/// @notice Wrapper for BLS precompiles based on https://github.com/ethereum/EIPs/blob/master/EIPS/eip-2537.md

library BLS {
    struct Fp {
        uint256 a;
        uint256 b;
    }

    struct Fp2 {
        Fp c0;
        Fp c1;
    }

    struct G1Point {
        Fp x;
        Fp y;
    }

    struct G2Point {
        Fp2 x;
        Fp2 y;
    }

    function pairingCheck(
        G1Point[] memory g1Points,
        G2Point[] memory g2Points
    ) internal view returns (bool result) {}

    function mapToG1(Fp memory p) internal view returns (G1Point memory) {}

    function mapToG2(Fp2 memory p) internal view returns (G2Point memory) {}

    function hashToG2(
        bytes memory message
    ) internal view returns (G2Point memory) {}

    function expandMsgXmd(
        bytes memory message,
        bytes memory dst
    ) private pure returns (bytes32[] memory) {}

    function mod(bytes32 a, bytes32 b) private pure returns (Fp memory p) {}
}
