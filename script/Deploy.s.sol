// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Script, console} from "forge-std/Script.sol";
import {BLSVerify} from "../src/BLSVerify.sol";
import {PayToExit} from "../src/PayToExit.sol";
import {PayToAttest} from "../src/PayToAttest.sol";
import {PayToBias} from "../src/PayToBias.sol";
import {HeaderVerify} from "../src/HeaderVerify.sol";

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        console.log("Deploying contracts to chain ID:", block.chainid);
        console.log("Deployer address:", vm.addr(deployerPrivateKey));

        // Deploy verification libraries
        console.log("Deploying BLSVerify...");
        BLSVerify blsVerify = new BLSVerify();
        console.log("BLSVerify deployed at:", address(blsVerify));

        console.log("Deploying HeaderVerify...");
        HeaderVerify headerVerify = new HeaderVerify();
        console.log("HeaderVerify deployed at:", address(headerVerify));

        // Deploy bribery contracts
        console.log("Deploying PayToExit...");
        PayToExit payToExit = new PayToExit(address(blsVerify));
        console.log("PayToExit deployed at:", address(payToExit));

        console.log("Deploying PayToAttest...");
        PayToAttest payToAttest = new PayToAttest(address(blsVerify));
        console.log("PayToAttest deployed at:", address(payToAttest));

        console.log("Deploying PayToBias...");
        PayToBias payToBias = new PayToBias(address(headerVerify));
        console.log("PayToBias deployed at:", address(payToBias));

        vm.stopBroadcast();

        console.log("\n=== Deployment Complete ===");
        console.log("BLSVerify:", address(blsVerify));
        console.log("HeaderVerify:", address(headerVerify));
        console.log("PayToExit:", address(payToExit));
        console.log("PayToAttest:", address(payToAttest));
        console.log("PayToBias:", address(payToBias));
    }
}
