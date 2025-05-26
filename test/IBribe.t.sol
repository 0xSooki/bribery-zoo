// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Test} from "forge-std/Test.sol";
import {IBribe} from "../src/IBribe.sol";
import {PayToExit} from "../src/PayToExit.sol";
import {PayToFork} from "../src/PayToFork.sol";

contract MinimalBribeInterfaceTest is Test {
    PayToExit public payToExit;
    PayToFork public payToFork;
    IBribe public bribeInterface;

    address public owner;
    uint256 constant INITIAL_BRIBE_AMOUNT = 1 ether;

    function setUp() public {
        owner = address(this);

        // Deploy contracts
        payToExit = new PayToExit{value: 5 ether}(INITIAL_BRIBE_AMOUNT);
        payToFork = new PayToFork{value: 3 ether}();
    }

    function testPayToExitInterface() public {
        bribeInterface = IBribe(address(payToExit));

        // Test basic interface functions
        assertEq(bribeInterface.owner(), owner);
        assertEq(bribeInterface.bribeAmount(), INITIAL_BRIBE_AMOUNT);

        // Test updateBribeAmount
        uint256 newAmount = 2 ether;
        bribeInterface.updateBribeAmount(newAmount);
        assertEq(bribeInterface.bribeAmount(), newAmount);

        // Test fund management
        uint256 balanceBefore = address(payToExit).balance;
        bribeInterface.depositFunds{value: 1 ether}();
        assertEq(address(payToExit).balance, balanceBefore + 1 ether);

        bribeInterface.withdrawFunds(1 ether);
        assertEq(address(payToExit).balance, balanceBefore);
    }

    function testPayToForkInterface() public {
        bribeInterface = IBribe(address(payToFork));

        // Test basic interface functions
        assertEq(bribeInterface.owner(), owner);
        assertEq(bribeInterface.bribeAmount(), 0); // PayToFork starts with 0

        // Test updateBribeAmount
        uint256 newAmount = 2 ether;
        bribeInterface.updateBribeAmount(newAmount);
        assertEq(bribeInterface.bribeAmount(), newAmount);

        // Test fund management
        uint256 balanceBefore = address(payToFork).balance;
        bribeInterface.depositFunds{value: 1 ether}();
        assertEq(address(payToFork).balance, balanceBefore + 1 ether);

        bribeInterface.withdrawFunds(1 ether);
        assertEq(address(payToFork).balance, balanceBefore);
    }

    receive() external payable {}
}
