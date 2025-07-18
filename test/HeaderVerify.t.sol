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
    function testVerifyBlockhash() public view {
        // Real mainnet block 22916101 header data
        HeaderVerify.BlockHeader memory header = HeaderVerify.BlockHeader({
            parentHash: 0x7717e103fab2d799f8e4106d4554e5132ca9ad5156f6f16fa7d21c767256ba4f,
            sha3Uncles: 0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347,
            miner: 0x4838B106FCe9647Bdf1E7877BF73cE8B0BAD5f97,
            stateRoot: 0xb6a6a4f21cb3732b89690b552d5c39c718dd43275eecb0f9167bd71bb8e2f7ce,
            transactionsRoot: 0x333b983a945c9ace9d3c58021ac4e911d054c4bc912d705d1d11426be44619dc,
            receiptsRoot: 0x6c942cc4d783951e52e52c11b2fb17e0574af3c664d66170521a93d80aff9a38,
            logsBloom: hex"81ea2be709f579def272335384189cb09b47851dc4f6d0ee31f76e9126f1863bd55cafb6ea4ea0fefe727bd76f0f9399df2cf2b49d9b6cf247e3bcd1292e63a5722495b9614f9f0dce8f792e92c132e29ece37b361474e6038337c62a82407d04c7de81cebef06f67454d5e27f656fbfb1379bfe8710cc4dd7387a94a27fd69f6926a3b91065cf39485df74d3f366b7646998f5515937b59fc7bd7f745b57efeabdc31ea53f07dc00ef21fc67f57cede22c65ebfcfbb5459cc7f65df7935587afd977e5a44c82be9f16fb8d65b62fd556de5645fcf7894d41edf7152f1f0fb7bf3f33c0195b2adf091e4f2ecf1f13be5ff4dba22511c9ec7d4b9d7d298ef5627",
            difficulty: 0,
            number: 0x15d9085, // 22909061 in decimal
            gasLimit: 0x2277537,
            gasUsed: 0x11437cb,
            timestamp: 0x68736e03,
            extraData: hex"546974616e2028746974616e6275696c6465722e78797a29",
            mixHash: 0x1594d24382ef583d1e1be9412b4a59ee3b401debf5cba382b824ef07110b64fa,
            nonce: 0x0000000000000000,
            baseFeePerGas: 0x167675bd,
            withdrawalsRoot: 0x1f0186dfc6bef700c3fb9d867d6cc49c1cf1be4bbc0505796a0b46886db67b8d,
            blobGasUsed: 0x0,
            excessBlobGas: 0x20000,
            parentBeaconBlockRoot: 0xce765cd034ba2f51e2c91a4111ec40b7b0fdd6dbc0996b58b5e35e3ff8b6ed43,
            requestsHash: 0xe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
        });

        // Expected hash for block 22916101
        bytes32 expectedHash = 0x23254aeb7f8e36fa7baa8ea2df34c8a3896a6c31dce92546adc7b9598d4ae590;

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
