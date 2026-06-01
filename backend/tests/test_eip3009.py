"""EIP-3009 transferWithAuthorization builder/signer tests."""

from eth_account import Account

from intent_guard import eip3009

USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
MERCHANT = "0x1111111111111111111111111111111111111111"


def test_build_and_sign_authorization():
    key = "0x" + "44" * 32
    sender = Account.from_key(key).address
    built = eip3009.build_authorization(
        sender=sender, to=MERCHANT, value=4_000_000,
        valid_after=0, valid_before=2**48, token=USDC, chain_id=84532,
        nonce="0x" + "cd" * 32,
    )
    assert built["authorization"]["to"].lower() == MERCHANT.lower()
    sig = eip3009.sign_authorization(built["typed_data"], key)
    assert sig.startswith("0x") and len(sig) == 132  # 65-byte sig


def test_authorization_signature_recovers():
    from eth_account.messages import encode_typed_data
    key = "0x" + "55" * 32
    sender = Account.from_key(key).address
    built = eip3009.build_authorization(
        sender=sender, to=MERCHANT, value=1, valid_after=0, valid_before=2**48,
        token=USDC, chain_id=84532,
    )
    sig = eip3009.sign_authorization(built["typed_data"], key)
    signable = encode_typed_data(full_message=built["typed_data"])
    assert Account.recover_message(signable, signature=sig).lower() == sender.lower()
