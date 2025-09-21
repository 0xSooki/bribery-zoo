# Bribery zoo

[![License](https://img.shields.io/github/license/0xSooki/bribery-zoo)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/0xSooki/bribery-zoo/test.yml)](https://github.com/0xSooki/randao-bribery-market/actions)
[![Foundry](https://img.shields.io/badge/Built%20with-Foundry-FFDB1C.svg)](https://getfoundry.sh/)
[![Solidity](https://img.shields.io/badge/Solidity-^0.8.0-363636?logo=solidity)](https://soliditylang.org/)
[![GitHub stars](https://img.shields.io/github/stars/0xSooki/randao-bribery-market)](https://github.com/0xSooki/bribery-zoo/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/0xSooki/randao-bribery-market)](https://github.com/0xSooki/bribery-zoo/issues)

<p align="center">
  <img src="https://github.com/user-attachments/assets/42e36f00-1082-4016-aafb-c4e4e8cbafcc" alt="bribzoo" width="700">
</p>

This repository contains smart contracts for bribery attacks in Ethereum's Proof-of-Stake consensus mechanism. The project implements multiple types of bribery attacks to conduct research on their efficiency.

## 🎯 Overview

This project explores potential vulnerabilities in Ethereum's consensus layer by implementing various bribery attack vectors:

- **PayToExit**: Incentivizes validators to voluntarily exit the network
- **PayToAttest**: Bribes validators to attest to specific beacon chain data
- **PayToBias**: Manipulates RANDAO randomness by incentivizing specific validator behavior

## 📁 Project Structure

```text
src/
├── IBribe.sol          # Unified bribery interface
├── PayToExit.sol       # Validator exit bribery attacks
├── PayToAttest.sol     # Attestation manipulation attacks
├── PayToBias.sol       # RANDAO randomness manipulation
├── BLSVerify.sol       # BLS signature verification utilities
├── HeaderVerify.sol    # Block header verification utilities
└── Utils.sol           # Common utility functions

test/
├── PayToExit.t.sol     # Exit bribery tests
├── PayToAttest.t.sol   # Attestation tests
├── PayToBias.t.sol     # RANDAO bias tests
├── BLSVerify.t.sol     # BLS verification tests
├── HeaderVerify.t.sol  # Header verification tests
└── BLSVerifyGas.t.sol  # Gas optimization tests
```

## 🚀 Quick Start

### Prerequisites

- [Foundry](https://book.getfoundry.sh/getting-started/installation) (latest version)
- Git
- Python 3.8+

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/0xSooki/bribery-zoo.git
   cd bribery-zoo
   ```

2. **Install dependencies**:
   ```bash
   git submodule update --init --recursive
   forge install
   ```

3. **Build the contracts**:
   ```bash
   forge build
   ```

4. **Run tests**:
   ```bash
   forge test
   ```

## 🧪 Testing

The project includes test coverage.

### Run All Tests
```bash
forge test
```

### Run Tests with Gas Reports
```bash
forge test --gas-report
```

### Run Specific Test Contract
```bash
forge test --match-contract PayToExitTest
forge test --match-contract PayToAttestTest
forge test --match-contract PayToBiasTest
```

### Run Specific Test Function
```bash
forge test --match-test testWithGeneratedData
```

## 📋 Contract Deployment

### Local Deployment (Anvil)

1. **Start a local Ethereum node**:
   ```bash
   anvil
   ```

2. **Deploy contracts** (in a new terminal):
   ```bash
   # Deploy BLS verification library first
   forge create src/BLSVerify.sol:BLSVerify \
     --rpc-url http://localhost:8545 \
     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

   # Deploy PayToExit (replace BLS_ADDRESS with actual deployed address)
   forge create src/PayToExit.sol:PayToExit \
     --constructor-args "BLS_ADDRESS" \
     --rpc-url http://localhost:8545 \
     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
   ```

### Testnet Deployment

For testnet deployment, update the RPC URL and private key:

```bash
# Example for Sepolia testnet
forge create src/BLSVerify.sol:BLSVerify \
  --rpc-url https://rpc.sepolia.org \
  --private-key YOUR_PRIVATE_KEY \
  --verify --etherscan-api-key YOUR_ETHERSCAN_API_KEY

# Deploy other contracts with BLS address
forge create src/PayToExit.sol:PayToExit \
  --constructor-args "DEPLOYED_BLS_ADDRESS" \
  --rpc-url https://rpc.sepolia.org \
  --private-key YOUR_PRIVATE_KEY \
  --verify --etherscan-api-key YOUR_ETHERSCAN_API_KEY
```

### Deployment Script

Create a deployment script in `script/Deploy.s.sol`:

Run with:
```bash
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
```
