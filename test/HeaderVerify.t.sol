// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {HeaderVerify} from "../src/HeaderVerify.sol";

/**
 * @title HeaderVerifyTest
 * @notice Test suite for Cancun-era block header verification
 * @dev All tests use the 21-field Cancun format
 */
contract HeaderVerifyTest is Test {
    HeaderVerify public headerVerify;

    function setUp() public {
        headerVerify = new HeaderVerify();
    }

    /**
     * @notice Single test to verify computed hash matches expected hash for block 22916101
     * @dev This test uses real mainnet block 22916101 data to ensure hash computation is correct
     */
    function testVerifyBlockhash() public {
        // Real mainnet block 22916101 header data
        HeaderVerify.BlockHeader memory header = HeaderVerify.BlockHeader({
            parentHash: 0x71f36f0edbffb49d3885ac4e311dfb61088945b6f5a0797a8038dd3764821424,
            sha3Uncles: 0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347,
            miner: 0x7DbfeD5686847113b527DC215DBA4E332DF8cc6c,
            stateRoot: 0x5f73b9a9f02e7e47c1c87ddfbf06f9e84ff03fc9b227a15a749748f8154677bf,
            transactionsRoot: 0x16849e354a35712b40ee99e96288f8b36fec8005db4e0cd7b240bee52743520d,
            receiptsRoot: 0x5599b4da2a7208958b0392990c3c14ba297223110f16b62863daa4d1d8dd29f7,
            logsBloom: hex"11fe39f049c0887a36e5045ddae29dd173d498b944c431591a3b0410e62e8887128c491d90c842274f252b331d1613b1c7e3d84088a420007bcd3ec029ae69dac9ce1848efbcf30ee941636e9e44b1a008641dbf176c68a4e07e986c8d6010174ee3f16c0b762c22a66dad9058c44a11db1d9e402dd5a647b71ac1d6531f780a3e3aaf48bccbc97f78d8046803236726b10e9d717b902caa8e6fa9d368b83568174638fe01f0b212829536de661823ba30645205a421d7088b6f3c73114829f57f6787126a581f132489536c02eb1a262915264205ac997143d3e7cebc04224f4452acc4a514e09d832e96a50ac358d36f29f853415442c7660199e2116d4527",
            difficulty: 0,
            number: 22916101,
            gasLimit: 36140617,
            gasUsed: 12169751,
            timestamp: 1752480215,
            extraData: hex"4275696c6465722b207777772e627463732e636f6d2f6275696c646572",
            mixHash: 0x6f74c123e3532e124b6a263c3755c163bc6940f04feec2b090f4aadec90af618,
            nonce: 0x0000000000000000,
            baseFeePerGas: 1716818952,
            withdrawalsRoot: 0xd6e43380ed12db043113c66feae84e345b46a059feabeabad78d1dab54261cbc,
            blobGasUsed: 131072,
            excessBlobGas: 393216,
            parentBeaconBlockRoot: 0xec61dae56c8fdba45cdf7232a3cb0ca7d2e9ba2e8fabe6f9df3a2c0bd6b5ad3f,
            requestsHash: 0xe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
        });

        // Expected hash for block 22916101
        bytes32 expectedHash = 0x860630231fb0e55d713ad11ab0bd79ba09dcf2017ecc5aaf43206a097b765ec2;

        // Get computed hash from contract
        bytes32 computedHash = headerVerify.getComputedHash(header);

        assertEq(computedHash, expectedHash, "Computed hash must match expected hash for block 22916101");

        console.log("Block 22916101 hash verification:");
        console.log("Expected: ");
        console.logBytes32(expectedHash);
        console.log("Computed: ");
        console.logBytes32(computedHash);
        console.log("Match: ", computedHash == expectedHash);
    }
}
