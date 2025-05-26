// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";

/**
 * @title IBribe
 * @dev Minimal unified interface for validator bribing contracts
 * @notice Each contract implements takeBribe with their specific signature
 */
interface IBribe {
    /**
     * @dev Get the current bribe amount
     * @return amount The bribe amount in wei
     */
    function bribeAmount() external view returns (uint256 amount);

    /**
     * @dev Get the contract owner
     * @return owner The owner address
     */
    function owner() external view returns (address owner);

    /**
     * @dev Update the bribe amount (owner only)
     * @param _newBribeAmount The new bribe amount
     */
    function updateBribeAmount(uint256 _newBribeAmount) external;

    /**
     * @dev Deposit funds for bribes (owner only)
     */
    function depositFunds() external payable;

    /**
     * @dev Withdraw funds (owner only)
     * @param amount Amount to withdraw
     */
    function withdrawFunds(uint256 amount) external;

    /**
     * @dev Take bribe - PayToExit version
     * @param validatorIndex The validator index
     * @param pubkey The validator's public key
     * @param signature The BLS signature on the VoluntaryExit object
     * @param message The VoluntaryExit object
     * @param depositProof Merkle proof for deposit
     * @param depositRoot The deposit root
     * @param deposit_count The deposit count
     */
    function takeBribe(
        uint256 validatorIndex,
        BLS.G1Point calldata pubkey,
        BLS.G2Point calldata signature,
        bytes memory message,
        bytes32[] calldata depositProof,
        bytes32 depositRoot,
        uint64 deposit_count
    ) external;

    /**
     * @dev Take bribe - PayToFork version
     * @param signature The BLS signature on the attestation data
     */
    function takeBribe(BLS.G2Point calldata signature) external;
}
