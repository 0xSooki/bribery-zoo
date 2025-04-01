import "forge-std/Test.sol";
import "../src/RANDAORevealBriberyMarket.sol";

contract RANDAORevealBriberyMarketTest is Test {
    RANDAORevealBriberyMarket market;

    function setUp() public {
        market = new RANDAORevealBriberyMarket();
    }
}
