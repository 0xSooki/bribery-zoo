// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {console} from "forge-std/console.sol";
import {HeaderVerify} from "../src/HeaderVerify.sol";

contract BLSVerifyGasTest is Test {
    BLSVerify blsVerify;
    HeaderVerify headerVerify;

    function setUp() public {
        blsVerify = new BLSVerify();
        headerVerify = new HeaderVerify();
    }

    function testGasCostsDifferentMessage() public view {
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
                privKeys[i] = bytes32(uint256(keccak256(abi.encodePacked("key_", i))));

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
        for (uint256 n = 1; n <= 25; n++) {
            BLS.G1Point[] memory pubKeys = new BLS.G1Point[](n);
            BLS.G2Point[] memory sigs = new BLS.G2Point[](n);
            bytes32[] memory privKeys = new bytes32[](n);
            bytes memory message = "test";

            BLS.G1Point[] memory g1gen = new BLS.G1Point[](1);
            g1gen[0] = blsVerify.G1_GEN();

            for (uint256 i = 0; i < n; i++) {
                privKeys[i] = bytes32(uint256(keccak256(abi.encodePacked("key_", i))));

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
            uint256 gasPerMessage = gasUsed;

            assertTrue(result, "Verification should succeed");
            console.log("%d, %d, %d", n, gasUsed, gasPerMessage);
        }
    }

    function testPayToBiasCost() public {
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

        uint256 blockNumber = 0x15d9085;

        for (uint256 i = 2; i < 32; i++) {
            HeaderVerify.BlockHeader[] memory headers = new HeaderVerify.BlockHeader[](i);
            headers[0] = header;

            for (uint256 j = 1; j < i; j++) {
                // Create a proper copy of the previous header
                HeaderVerify.BlockHeader memory temp = HeaderVerify.BlockHeader({
                    parentHash: headers[j - 1].parentHash,
                    sha3Uncles: headers[j - 1].sha3Uncles,
                    miner: headers[j - 1].miner,
                    stateRoot: headers[j - 1].stateRoot,
                    transactionsRoot: headers[j - 1].transactionsRoot,
                    receiptsRoot: headers[j - 1].receiptsRoot,
                    logsBloom: headers[j - 1].logsBloom,
                    difficulty: headers[j - 1].difficulty,
                    number: blockNumber + j, // Set the correct block number
                    gasLimit: headers[j - 1].gasLimit,
                    gasUsed: headers[j - 1].gasUsed,
                    timestamp: headers[j - 1].timestamp,
                    extraData: headers[j - 1].extraData,
                    mixHash: headers[j - 1].mixHash,
                    nonce: headers[j - 1].nonce,
                    baseFeePerGas: headers[j - 1].baseFeePerGas,
                    withdrawalsRoot: headers[j - 1].withdrawalsRoot,
                    blobGasUsed: headers[j - 1].blobGasUsed,
                    excessBlobGas: headers[j - 1].excessBlobGas,
                    parentBeaconBlockRoot: headers[j - 1].parentBeaconBlockRoot,
                    requestsHash: headers[j - 1].requestsHash
                });
                temp.parentHash = headerVerify.getComputedHash(headers[j - 1]);
                headers[j] = temp;
            }

            bytes memory message = hex"ff68700314ec05cbcd76830a1e988a25ded0452a5dec504f6cb0d986dedf97b5"; // aggregate sig on epochs

            BLS.G1Point memory pubKey = BLS.G1Point(
                bytes32(uint256(13543975904092429560281716315864751138)),
                bytes32(uint256(111022849395952064956478265176174406830686766543213148271945602771187906920076)),
                bytes32(uint256(33472958331677899801220032596191519984)),
                bytes32(uint256(90583252102554656131046097583482158216567079391027065915371965747423183058778))
            );

            BLS.G2Point memory sig = BLS.G2Point(
                bytes32(uint256(12780674325596173921328184440545773457)),
                bytes32(uint256(83230619698717931381190252036444915591162734744112071986450428195886671827534)),
                bytes32(uint256(29838942989423688124672056096051238560)),
                bytes32(uint256(104803384101529698630264687588039042811790420927247773612256794282239749473259)),
                bytes32(uint256(27268916417469165602030417092070919301)),
                bytes32(uint256(61851856206544235472236738213275926630939133799962543086625283952273127329685)),
                bytes32(uint256(23773001621986189688304150713670191554)),
                bytes32(uint256(88592023272739319800459645347905619170309661461466421635503797174466009043477))
            );

            uint256 ogasBefore = gasleft();
            bool result = blsVerify.verify(message, sig, pubKey);
            uint256 ogasAfter = gasleft();
            assertTrue(result, "Valid signature should pass verification");

            uint256 tgasBefore = gasleft();
            for (uint256 j = 1; j < i; j++) {
                HeaderVerify.BlockHeader memory parentHeader = headers[j - 1];
                HeaderVerify.BlockHeader memory nextHeader = headers[j];

                require(parentHeader.number == blockNumber + j - 1, "Invalid parent block number");
                require(nextHeader.number == blockNumber + j, "Invalid next block number");

                vm.pauseGasMetering();
                bytes32 parentHash = headerVerify.getComputedHash(parentHeader);
                bytes32 nextHash = headerVerify.getComputedHash(nextHeader);
                vm.resumeGasMetering();

                require(parentHash != bytes32(0), "Parent block hash not available");
                require(nextHash != bytes32(0), "Next block hash not available");

                require(headerVerify.verifyBlockHash(parentHeader, parentHash), "Invalid parent block header or hash");
                require(headerVerify.verifyBlockHash(nextHeader, nextHash), "Invalid next block header or hash");

                require(
                    nextHeader.parentHash == parentHash,
                    "Next block should point to parent, proving validator block was skipped"
                );

                uint256 timeGap = nextHeader.timestamp - parentHeader.timestamp;

                if (timeGap > 12) {} else {}
            }
            uint256 tgasAfter = gasleft();
            console.log("%s, %s", tgasBefore - tgasAfter, ogasBefore - ogasAfter);
        }
    }
}
