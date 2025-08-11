// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {PayToBiasTestable} from "../src/PayToBiasTestable.sol";
import {PayToBias} from "../src/PayToBias.sol";
import {HeaderVerify} from "../src/HeaderVerify.sol";

contract PayToBiasTest is Test {
    PayToBiasTestable public payToBias;
    HeaderVerify public headerVerify;

    address public validator = address(0x123);
    address public bidder1 = address(0x2);
    address public bidder2 = address(0x3);

    uint256 public constant BLOCK_NUMBER = 1000;
    uint256 public constant EXPECTED_TIMESTAMP = 1752480215;
    uint256 public constant AUCTION_DEADLINE = EXPECTED_TIMESTAMP + 60;

    function setUp() public {
        headerVerify = new HeaderVerify();
        payToBias = new PayToBiasTestable(address(headerVerify));

        vm.deal(bidder1, 10 ether);
        vm.deal(bidder2, 10 ether);
        vm.deal(validator, 1 ether);

        vm.roll(1100);

        payToBias.setUseMockBlockhashes(true);
    }

    function testCreateAuction() public {
        vm.prank(validator);
        payToBias.createAuction(BLOCK_NUMBER, AUCTION_DEADLINE);

        PayToBias.ValidatorAuction memory auction = payToBias.getAuction(BLOCK_NUMBER);
        assertEq(auction.validator, validator);
        assertEq(auction.blockNumber, BLOCK_NUMBER);
        assertEq(auction.auctionDeadline, AUCTION_DEADLINE);
        assertFalse(auction.withhold);
        assertFalse(auction.claimed);
    }

    function testPlaceBids() public {
        vm.prank(validator);
        payToBias.createAuction(BLOCK_NUMBER, AUCTION_DEADLINE);

        // Bidder1 bets on publish
        vm.prank(bidder1);
        payToBias.placeBid{value: 1 ether}(BLOCK_NUMBER, true);

        // Bidder2 bets on withhold
        vm.prank(bidder2);
        payToBias.placeBid{value: 2 ether}(BLOCK_NUMBER, false);

        (PayToBias.Bid memory publishBid, PayToBias.Bid memory withholdBid) = payToBias.getHighestBids(BLOCK_NUMBER);

        assertEq(publishBid.bidder, bidder1);
        assertEq(publishBid.amount, 1 ether);
        assertTrue(publishBid.publishChoice);

        assertEq(withholdBid.bidder, bidder2);
        assertEq(withholdBid.amount, 2 ether);
        assertFalse(withholdBid.publishChoice);
    }

    function testSubmitValidBlockProof() public {
        vm.prank(validator);
        payToBias.createAuction(BLOCK_NUMBER, AUCTION_DEADLINE);

        vm.prank(bidder1);
        payToBias.placeBid{value: 1 ether}(BLOCK_NUMBER, false);

        // Create parent block header (block N-1)
        HeaderVerify.BlockHeader memory parentHeader = HeaderVerify.BlockHeader({
            parentHash: 0x61f36f0edbffb49d3885ac4e311dfb61088945b6f5a0797a8038dd3764821424,
            sha3Uncles: 0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347,
            miner: address(0x456),
            stateRoot: 0x4f73b9a9f02e7e47c1c87ddfbf06f9e84ff03fc9b227a15a749748f8154677bf,
            transactionsRoot: 0x16849e354a35712b40ee99e96288f8b36fec8005db4e0cd7b240bee52743520d,
            receiptsRoot: 0x5599b4da2a7208958b0392990c3c14ba297223110f16b62863daa4d1d8dd29f7,
            logsBloom: hex"11fe39f049c0887a36e5045ddae29dd173d498b944c431591a3b0410e62e8887128c491d90c842274f252b331d1613b1c7e3d84088a420007bcd3ec029ae69dac9ce1848efbcf30ee941636e9e44b1a008641dbf176c68a4e07e986c8d6010174ee3f16c0b762c22a66dad9058c44a11db1d9e402dd5a647b71ac1d6531f780a3e3aaf48bccbc97f78d8046803236726b10e9d717b902caa8e6fa9d368b83568174638fe01f0b212829536de661823ba30645205a421d7088b6f3c73114829f57f6787126a581f132489536c02eb1a262915264205ac997143d3e7cebc04224f4452acc4a514e09d832e96a50ac358d36f29f853415442c7660199e2116d4527",
            difficulty: 0,
            number: BLOCK_NUMBER - 1,
            gasLimit: 36140617,
            gasUsed: 12169751,
            timestamp: EXPECTED_TIMESTAMP - 12, // 12 seconds before
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

        // Create validator block header (block N)
        HeaderVerify.BlockHeader memory validatorHeader = HeaderVerify.BlockHeader({
            parentHash: 0x0, // Will be set to parent hash
            sha3Uncles: 0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347,
            miner: validator,
            stateRoot: 0x5f73b9a9f02e7e47c1c87ddfbf06f9e84ff03fc9b227a15a749748f8154677bf,
            transactionsRoot: 0x16849e354a35712b40ee99e96288f8b36fec8005db4e0cd7b240bee52743520d,
            receiptsRoot: 0x5599b4da2a7208958b0392990c3c14ba297223110f16b62863daa4d1d8dd29f7,
            logsBloom: hex"11fe39f049c0887a36e5045ddae29dd173d498b944c431591a3b0410e62e8887128c491d90c842274f252b331d1613b1c7e3d84088a420007bcd3ec029ae69dac9ce1848efbcf30ee941636e9e44b1a008641dbf176c68a4e07e986c8d6010174ee3f16c0b762c22a66dad9058c44a11db1d9e402dd5a647b71ac1d6531f780a3e3aaf48bccbc97f78d8046803236726b10e9d717b902caa8e6fa9d368b83568174638fe01f0b212829536de661823ba30645205a421d7088b6f3c73114829f57f6787126a581f132489536c02eb1a262915264205ac997143d3e7cebc04224f4452acc4a514e09d832e96a50ac358d36f29f853415442c7660199e2116d4527",
            difficulty: 0,
            number: BLOCK_NUMBER,
            gasLimit: 36140617,
            gasUsed: 12169751,
            timestamp: EXPECTED_TIMESTAMP,
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

        // Compute hashes
        bytes32 parentHash = headerVerify.getComputedHash(parentHeader);

        // Set parent hash references
        validatorHeader.parentHash = parentHash;
        bytes32 validatorHash = headerVerify.getComputedHash(validatorHeader);

        // Set mock blockhashes to match computed hashes
        payToBias.setMockBlockhash(BLOCK_NUMBER - 1, parentHash);
        payToBias.setMockBlockhash(BLOCK_NUMBER, validatorHash);

        uint256 validatorBalanceBefore = validator.balance;

        vm.warp(AUCTION_DEADLINE + 5);
        vm.prank(validator);
        payToBias.takeBribe(BLOCK_NUMBER, parentHeader, validatorHeader);

        PayToBias.ValidatorAuction memory auction = payToBias.getAuction(BLOCK_NUMBER);
        assertFalse(auction.withhold);
        assertTrue(auction.claimed);

        // Validator should receive the winning bid
        assertEq(validator.balance, validatorBalanceBefore + 1 ether);
    }

    function testClaimWithholdingWithProof() public {
        vm.prank(validator);
        payToBias.createAuction(BLOCK_NUMBER, AUCTION_DEADLINE);

        vm.prank(bidder2);
        payToBias.placeBid{value: 2 ether}(BLOCK_NUMBER, true);

        // Create parent block header (block N-1)
        HeaderVerify.BlockHeader memory parentHeader = HeaderVerify.BlockHeader({
            parentHash: 0x61f36f0edbffb49d3885ac4e311dfb61088945b6f5a0797a8038dd3764821424,
            sha3Uncles: 0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347,
            miner: address(0x456),
            stateRoot: 0x4f73b9a9f02e7e47c1c87ddfbf06f9e84ff03fc9b227a15a749748f8154677bf,
            transactionsRoot: 0x16849e354a35712b40ee99e96288f8b36fec8005db4e0cd7b240bee52743520d,
            receiptsRoot: 0x5599b4da2a7208958b0392990c3c14ba297223110f16b62863daa4d1d8dd29f7,
            logsBloom: hex"11fe39f049c0887a36e5045ddae29dd173d498b944c431591a3b0410e62e8887128c491d90c842274f252b331d1613b1c7e3d84088a420007bcd3ec029ae69dac9ce1848efbcf30ee941636e9e44b1a008641dbf176c68a4e07e986c8d6010174ee3f16c0b762c22a66dad9058c44a11db1d9e402dd5a647b71ac1d6531f780a3e3aaf48bccbc97f78d8046803236726b10e9d717b902caa8e6fa9d368b83568174638fe01f0b212829536de661823ba30645205a421d7088b6f3c73114829f57f6787126a581f132489536c02eb1a262915264205ac997143d3e7cebc04224f4452acc4a514e09d832e96a50ac358d36f29f853415442c7660199e2116d4527",
            difficulty: 0,
            number: BLOCK_NUMBER - 1,
            gasLimit: 36140617,
            gasUsed: 12169751,
            timestamp: EXPECTED_TIMESTAMP - 12,
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

        HeaderVerify.BlockHeader memory nextHeader = HeaderVerify.BlockHeader({
            parentHash: 0x0, // Will be set to parent hash (skipping validator block)
            sha3Uncles: 0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347,
            miner: address(0x789),
            stateRoot: 0x6f73b9a9f02e7e47c1c87ddfbf06f9e84ff03fc9b227a15a749748f8154677bf,
            transactionsRoot: 0x16849e354a35712b40ee99e96288f8b36fec8005db4e0cd7b240bee52743520d,
            receiptsRoot: 0x5599b4da2a7208958b0392990c3c14ba297223110f16b62863daa4d1d8dd29f7,
            logsBloom: hex"11fe39f049c0887a36e5045ddae29dd173d498b944c431591a3b0410e62e8887128c491d90c842274f252b331d1613b1c7e3d84088a420007bcd3ec029ae69dac9ce1848efbcf30ee941636e9e44b1a008641dbf176c68a4e07e986c8d6010174ee3f16c0b762c22a66dad9058c44a11db1d9e402dd5a647b71ac1d6531f780a3e3aaf48bccbc97f78d8046803236726b10e9d717b902caa8e6fa9d368b83568174638fe01f0b212829536de661823ba30645205a421d7088b6f3c73114829f57f6787126a581f132489536c02eb1a262915264205ac997143d3e7cebc04224f4452acc4a514e09d832e96a50ac358d36f29f853415442c7660199e2116d4527",
            difficulty: 0,
            number: BLOCK_NUMBER,
            gasLimit: 36140617,
            gasUsed: 12169751,
            timestamp: EXPECTED_TIMESTAMP + 25, // 25 seconds later (>12s gap proves missing block)
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

        bytes32 parentHash = headerVerify.getComputedHash(parentHeader);

        nextHeader.parentHash = parentHash;
        bytes32 nextHash = headerVerify.getComputedHash(nextHeader);

        payToBias.setMockBlockhash(BLOCK_NUMBER - 1, parentHash);
        payToBias.setMockBlockhash(BLOCK_NUMBER, nextHash);

        vm.warp(EXPECTED_TIMESTAMP + 25 + 1);

        uint256 validatorBalanceBefore = validator.balance;

        payToBias.takeBribe(BLOCK_NUMBER, parentHeader, nextHeader);

        PayToBias.ValidatorAuction memory auction = payToBias.getAuction(BLOCK_NUMBER);
        assertTrue(auction.withhold);
        assertTrue(auction.claimed);

        // Validator should receive the withhold bid
        assertEq(validator.balance, validatorBalanceBefore + 2 ether);
    }

    function testWithdrawFunds() public {
        vm.prank(validator);
        payToBias.createAuction(BLOCK_NUMBER, AUCTION_DEADLINE);

        vm.prank(bidder1);
        payToBias.placeBid{value: 1 ether}(BLOCK_NUMBER, true);

        vm.prank(bidder2);
        payToBias.placeBid{value: 2 ether}(BLOCK_NUMBER, true);

        assertEq(payToBias.balances(bidder1), 1 ether);

        uint256 bidder1BalanceBefore = bidder1.balance;
        vm.prank(bidder1);
        payToBias.withdrawFunds();

        assertEq(bidder1.balance, bidder1BalanceBefore + 1 ether);
        assertEq(payToBias.balances(bidder1), 0);
    }
}
