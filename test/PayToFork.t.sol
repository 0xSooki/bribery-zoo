// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/PayToFork.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";

contract PayToForkTest is Test {
    PayToFork payToFork;

    function setUp() public {
        payToFork = new PayToFork();
        vm.deal(address(payToFork), 10 ether);
    }

    function testTakeBribe() public {
        bytes memory attestData = hex"ff68700314ec05cbcd76830a1e988a25ded0452a5dec504f6cb0d986dedf97b5";

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
        PayToFork.TargetHeader memory header = PayToFork.TargetHeader({AggPubkey: pubKey, attestData: attestData});

        payToFork.defineTargetHeader(header, 2 ether);

        payToFork.takeBribe(sig);

        assertEq(payToFork.payout(address(this)), 2 ether);

        payToFork.declareForkSuccess();

        uint256 balanceBefore = address(this).balance;
        payToFork.withdrawPayout();
        uint256 balanceAfter = address(this).balance;

        assertEq(balanceAfter - balanceBefore, 2 ether);
    }

    receive() external payable {}
}
