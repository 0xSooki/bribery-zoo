from py_ecc.bls.g2_primitives import pubkey_to_G1, signature_to_G2

from eth2spec.deneb import spec as eth_spec
from py_ecc.bls import G2ProofOfPossession as bls
import sys
from eth2spec.utils.ssz.ssz_typing import uint64, Bytes4, Bytes32

class MinimalFork:
    def __init__(self, previous_version: Bytes4, current_version: Bytes4, epoch: uint64):
        self.previous_version = previous_version
        self.current_version = current_version
        self.epoch = epoch

class MinimalBeaconState:
    def __init__(self, fork: MinimalFork, genesis_validators_root: Bytes32):
        self.fork = fork
        self.genesis_validators_root = genesis_validators_root

def get_randao_signing_root(state: MinimalBeaconState,
                            epoch: uint64,
                            ) -> Bytes32:
    domain = eth_spec.get_domain(
        state=state,
        domain_type=eth_spec.DOMAIN_RANDAO,
        epoch=epoch,
    )
    print(eth_spec.compute_fork_digest)

    signing_root = eth_spec.compute_signing_root(epoch, domain)
    return signing_root


def split_fp48_to_limbs(n):
    hex_str = hex(n)[2:].zfill(96)
    high = int(hex_str[:32], 16)
    low = int(hex_str[32:], 16)
    return high, low

if __name__ == '__main__':

    GENESIS_VALIDATORS_ROOT = Bytes32.fromhex("4b363db94e286120d76eb905340fdd4e54bfe9f06bf33ff6cf5ad27f511bfe95")

    target_epoch = uint64(358926) 


    PREVIOUS_FORK_VERSION = Bytes4.fromhex("03000000")
    CURRENT_FORK_VERSION = Bytes4.fromhex("04000000")
    FORK_EPOCH = uint64(269568) 

    minimal_fork = MinimalFork(
        previous_version=PREVIOUS_FORK_VERSION,
        current_version=CURRENT_FORK_VERSION,
        epoch=FORK_EPOCH
    )
    minimal_state = MinimalBeaconState(
        fork=minimal_fork,
        genesis_validators_root=GENESIS_VALIDATORS_ROOT
    )

    try:
        randao_signing_root = get_randao_signing_root(
            state=minimal_state,
            epoch=target_epoch
        )

        sig = "b672c5793d565b6d0627a5b59bb516a0e7b49d0138f5efdfdf4b4871edf3a9989a2d8ad9d222fe6a206f0afd772b43eb099d77e515cf65a2c0f8cd910c6e8791b802dc811ebf02392a2b41beeb13491b0a0991e99cccbcbe2d2be36ec063924e"
        pk = "aa30799178ce9f68ad5482bc3f6cdc22f574b4b6768cd8d31064ee7c5d180945f08e9953bbfae82a459e1a8f178c3e8c"
        msg = randao_signing_root.hex()
        print(msg)
        sig_for_wire = bytes.fromhex(sig)
        pk_for_wire = bytes.fromhex(pk)
        msg_for_wire = bytes.fromhex(msg)

        print(bls.Verify(
            pk_for_wire,
            msg_for_wire,
            sig_for_wire
        ))
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        print("Please ensure eth2spec is installed and check input values (fork versions, epoch).", file=sys.stderr)
  
  
    print("pubkey g1 point")
    print(pubkey_to_G1(pk_for_wire))
    print("signature g2 point")
    print(signature_to_G2(sig_for_wire))

    sig = signature_to_G2(sig_for_wire)

    x_c0_high, x_c0_low = split_fp48_to_limbs(sig[0].coeffs[0])
    x_c1_high, x_c1_low = split_fp48_to_limbs(sig[0].coeffs[1])
    y_c0_high, y_c0_low = split_fp48_to_limbs(sig[1].coeffs[0])
    y_c1_high, y_c1_low = split_fp48_to_limbs(sig[1].coeffs[1])

    print("Solidity-compatible limbs for X:")
    print("x_c0_high:", x_c0_high)
    print("x_c0_low :", x_c0_low)
    print("x_c1_high:", x_c1_high)
    print("x_c1_low :", x_c1_low)

    print("Solidity-compatible limbs for Y:")
    print("y_c0_high:", y_c0_high)
    print("y_c0_low :", y_c0_low)
    print("y_c1_high:", y_c1_high)
    print("y_c1_low :", y_c1_low)
    
    g1 = pubkey_to_G1(pk_for_wire)
    x_high, x_low = split_fp48_to_limbs(g1[0].n)
    y_high, y_low = split_fp48_to_limbs(g1[1].n)
    z_high, z_low = split_fp48_to_limbs(g1[2].n)
    print("Solidity-compatible limbs for G1 X:")
    print("x_high:", x_high)
    print("x_low :", x_low)
    print("Solidity-compatible limbs for G1 Y:")
    print("y_high:", y_high)
    print("y_low :", y_low)
    print("Solidity-compatible limbs for G1 Z:")
    print("z_high:", z_high)
    print("z_low :", z_low)