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
}
