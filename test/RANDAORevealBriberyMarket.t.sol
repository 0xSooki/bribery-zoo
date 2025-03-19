import "forge-std/Test.sol";
import "../src/RANDAORevealBriberyMarket.sol";

contract RANDAORevealBriberyMarketTest is Test {
    RANDAORevealBriberyMarket market;

    function setUp() public {
        market = new RANDAORevealBriberyMarket();
    }

    function testConvertPublicKeyToG1() public view {
        bytes memory pubKey =
            hex"156c8a6a2c184569d69a76be144b5cdc5141d2d2ca4fe341f011e25e3969c55ad9e9b9ce2eb833c81a908e5fa4ac5f03";

        bytes memory resG1 =
            hex"00000000000000000000000000000000184bb665c37ff561a89ec2122dd343f20e0f4cbcaec84e3c3052ea81d1834e192c426074b02ed3dca4e7676ce4ce48ba0000000000000000000000000000000004407b8d35af4dacc809927071fc0405218f1401a6d15af775810e4e460064bcc9468beeba82fdc751be70476c888bf3";

        bytes memory result = market.convertPublicKeyToG1(pubKey);

        assertEq(result, resG1);
    }

    function testConvertInvalidPubKeyLength() public {
        bytes memory invalidPubKey = new bytes(40);
        vm.expectRevert();
        market.convertPublicKeyToG1(invalidPubKey);
    }

    function testConvertZeroPublicKey() public view {
        bytes memory zeroPubKey = new bytes(48);
        bytes memory result = market.convertPublicKeyToG1(zeroPubKey);

        assertGt(result.length, 0);
    }
}
