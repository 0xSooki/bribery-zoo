pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/RANDAORevealBriberyMarket.sol";

contract RANDAORevealBriberyMarketTest is Test {
    RANDAORevealBriberyMarket market;

    function setUp() public {
        market = new RANDAORevealBriberyMarket();
    }
}
