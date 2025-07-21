// SPDX-License-Identifier: MIT

library Utils {
    // Mainnet constants
    bytes4 public constant MAINNET_FORK_VERSION = 0x04000000;
    bytes32 public constant MAINNET_GENESIS_VALIDATORS_ROOT =
        0x4b363db94e286120d76eb905340fdd4e54bfe9f06bf33ff6cf5ad27f511bfe95;
    bytes4 public constant DOMAIN_VOLUNTARY_EXIT = 0x04000000;
    bytes4 public constant DOMAIN_ATTESTER = 0x01000000;

    /**
     * @notice Compute the signing root for a validator's voluntary exit
     * @param epoch The epoch when the validator wants to exit
     * @param validatorIndex The validator's index
     * @param forkVersion The current fork version
     * @param genesisValidatorsRoot The genesis validators root
     * @return signingRoot The signing root to be signed by the validator
     */
    function compute_signing_root(
        uint256 epoch,
        uint256 validatorIndex,
        bytes4 forkVersion,
        bytes32 genesisValidatorsRoot
    ) public pure returns (bytes32) {
        bytes32 voluntaryExitRoot = compute_voluntary_exit_root(
            epoch,
            validatorIndex
        );

        bytes32 domain = compute_domain(
            DOMAIN_VOLUNTARY_EXIT,
            MAINNET_FORK_VERSION,
            genesisValidatorsRoot
        );
        bytes32 signingRoot = sha256(
            abi.encodePacked(voluntaryExitRoot, domain)
        );

        return signingRoot;
    }

    /**
     * @notice Compute the SSZ hash tree root for VoluntaryExit
     * @param epoch The epoch
     * @param validatorIndex The validator index
     * @return The SSZ hash tree root
     */
    function compute_voluntary_exit_root(
        uint256 epoch,
        uint256 validatorIndex
    ) internal pure returns (bytes32) {
        bytes32 epochChunk = pad_to_32_bytes(epoch);
        bytes32 validatorIndexChunk = pad_to_32_bytes(validatorIndex);

        return merkle_root2(epochChunk, validatorIndexChunk);
    }

    /**
     * @notice Convert uint64 to SSZ chunk (32-byte padded, little-endian)
     * @param value The uint64 value to convert
     * @return 32-byte chunk with little-endian uint64 padded with zeros
     */
    function pad_to_32_bytes(uint256 value) internal pure returns (bytes32) {
        require(value <= type(uint64).max, "Value exceeds uint64 range");

        bytes8 littleEndianBytes = to_little_endian64(value);

        return bytes32(abi.encodePacked(littleEndianBytes, bytes24(0)));
    }

    /**
     * @notice Compute ETH2 domain following the specification
     * @param domainType The domain type (e.g., DOMAIN_VOLUNTARY_EXIT)
     * @param forkVersion The fork version
     * @param genesisValidatorsRoot The genesis validators root
     * @return domain The computed domain
     */
    function compute_domain(
        bytes4 domainType,
        bytes4 forkVersion,
        bytes32 genesisValidatorsRoot
    ) internal pure returns (bytes32 domain) {
        bytes32 forkDataRoot = merkle_root2(forkVersion, genesisValidatorsRoot);

        bytes memory domainBytes = new bytes(32);

        for (uint256 i = 0; i < 4; i++) {
            domainBytes[i] = domainType[i];
        }

        for (uint256 i = 0; i < 28; i++) {
            domainBytes[4 + i] = forkDataRoot[i];
        }

        domain = bytes32(domainBytes);
        return domain;
    }

    /**
     * @notice Convert uint256 to little-endian bytes8 for SSZ encoding
     * @param value The value to convert
     * @return Little-endian encoded bytes8
     */
    function to_little_endian64(uint256 value) internal pure returns (bytes8) {
        require(value <= type(uint64).max, "Value exceeds uint64 range");

        uint64 val = uint64(value);

        return
            bytes8(
                abi.encodePacked(
                    uint8(val),
                    uint8(val >> 8),
                    uint8(val >> 16),
                    uint8(val >> 24),
                    uint8(val >> 32),
                    uint8(val >> 40),
                    uint8(val >> 48),
                    uint8(val >> 56)
                )
            );
    }

    /**
     * @notice Compute merkle root for exactly 2 chunks
     * @param chunk1 First 32-byte chunk
     * @param chunk2 Second 32-byte chunk
     * @return Merkle root of the two chunks
     */
    function merkle_root2(
        bytes32 chunk1,
        bytes32 chunk2
    ) internal pure returns (bytes32) {
        return sha256(abi.encodePacked(chunk1, chunk2));
    }
}
