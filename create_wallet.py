#!/usr/bin/env python3
"""Create/reopen a portable Base Sepolia wallet, optionally funding it from an instructor wallet.

The wallet is an Ethereum EOA: the same address works on EVM chains, but this
script funds it ONLY on Base Sepolia (chain ID 84532).
"""

import argparse
import os
import secrets
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from eth_account import Account
from web3 import Web3

CHAIN_ID = 84532
DEFAULT_RPC = "https://sepolia.base.org"


def write_private(path: Path, text: str) -> None:
    """Create a private file, refusing to overwrite an existing one."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def load_password(wallet_dir: Path, env_var: str) -> str:
    pw_file = wallet_dir / ".password"
    if pw_file.is_file():
        return pw_file.read_text(encoding="utf-8").strip()
    password = os.getenv(env_var, "")
    if not password:
        raise RuntimeError(
            f"Missing {pw_file} and environment variable {env_var}. "
            "Cannot decrypt the existing keystore."
        )
    return password


def load_account(wallet_dir: Path, password_env: str):
    keystore_file = wallet_dir / "keystore.json"
    if not keystore_file.is_file():
        raise FileNotFoundError(f"Keystore not found: {keystore_file}")
    key = Account.decrypt(
        keystore_file.read_text(encoding="utf-8"),
        load_password(wallet_dir, password_env),
    )
    return Account.from_key(key)


def initialize_wallet(wallet_dir: Path):
    """Return (account, created), preserving any existing keystore."""
    wallet_dir.mkdir(parents=True, exist_ok=True)
    keystore_file = wallet_dir / "keystore.json"
    password_file = wallet_dir / ".password"
    address_file = wallet_dir / "address.txt"

    if keystore_file.exists():
        account = load_account(wallet_dir, "WALLET_PASSWORD")
        # address.txt is a convenience copy, NOT the source of wallet identity.
        if not address_file.exists() or address_file.read_text().strip() != account.address:
            address_file.write_text(account.address + "\n", encoding="utf-8")
        return account, False

    # Stop rather than silently reusing an orphaned password/address.
    if password_file.exists() or address_file.exists():
        raise RuntimeError(
            f"{wallet_dir} contains partial wallet files but no keystore. "
            "Restore a complete backup or choose an empty --wallet-dir."
        )

    account = Account.create()
    password = os.getenv("WALLET_PASSWORD") or secrets.token_urlsafe(32)
    encrypted = Account.encrypt(account.key, password)
    import json

    # Save the keystore first, so no unencrypted private key is persisted.
    write_private(keystore_file, json.dumps(encrypted, indent=2) + "\n")
    # Keep a complete portable backup in wallet/, including when the password
    # was supplied by an environment variable at creation time.
    write_private(password_file, password + "\n")
    write_private(address_file, account.address + "\n")
    return account, True


def rpc_connection(url: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 25}))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to Base Sepolia RPC: {url}")
    actual = w3.eth.chain_id
    if actual != CHAIN_ID:
        raise RuntimeError(f"Wrong network: chain ID {actual}; required {CHAIN_ID} (Base Sepolia)")
    return w3


def get_funder(funder_wallet_dir: str | None):
    if funder_wallet_dir:
        return load_account(Path(funder_wallet_dir).expanduser(), "FUNDER_WALLET_PASSWORD")
    private_key = os.getenv("FUNDER_PRIVATE_KEY", "").strip()
    if private_key:
        return Account.from_key(private_key)
    return None


def transfer_test_eth(w3: Web3, funder, recipient: str, grant_eth: str) -> str:
    if funder.address.lower() == recipient.lower():
        raise ValueError("Funder and recipient are the SAME wallet; refusing to transfer")
    try:
        amount = Decimal(grant_eth)
    except InvalidOperation as exc:
        raise ValueError("Grant must be a decimal ETH amount") from exc
    if amount <= 0:
        raise ValueError("Grant must be greater than zero")
    if amount.as_tuple().exponent < -18:
        raise ValueError("Grant cannot have more than 18 decimal places")
    amount_wei = int(amount * Decimal(10**18))
    gas_limit = 21_000
    # Legacy gasPrice transactions are accepted by Base Sepolia and keep this
    # introductory funding transaction easy to inspect in the explorer.
    gas_price = w3.eth.gas_price
    balance_wei = w3.eth.get_balance(funder.address)
    total_max_wei = amount_wei + gas_limit * gas_price
    if balance_wei < total_max_wei:
        raise RuntimeError(
            f"Insufficient instructor ETH: {Web3.from_wei(balance_wei, 'ether')} ETH, "
            f"requires at least {Web3.from_wei(total_max_wei, 'ether')} ETH"
        )
    tx = {
        "chainId": CHAIN_ID,
        "nonce": w3.eth.get_transaction_count(funder.address, "pending"),
        "from": funder.address,
        "to": Web3.to_checksum_address(recipient),
        "value": amount_wei,
        "gas": gas_limit,
        "gasPrice": gas_price,
    }
    signed = funder.sign_transaction(tx)
    tx_hash = Web3.to_hex(w3.eth.send_raw_transaction(signed.raw_transaction))
    print(f"Funding submitted: {tx_hash}", flush=True)
    print(f"Explorer: https://sepolia.basescan.org/tx/{tx_hash}", flush=True)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise RuntimeError(f"Funding transaction failed on-chain: {tx_hash}")
    return tx_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet-dir", default="wallet", help="Portable output directory; default: wallet")
    parser.add_argument(
        "--funder-wallet-dir", help="Existing instructor keystore directory (keystore.json + .password)"
    )
    parser.add_argument("--grant-eth", default="0.0001", help="ETH transferred if funding is enabled")
    parser.add_argument(
        "--top-up", action="store_true", help="Explicitly fund an EXISTING wallet again"
    )
    parser.add_argument("--rpc-url", default=os.getenv("BASE_SEPOLIA_RPC_URL", DEFAULT_RPC))
    args = parser.parse_args()

    wallet_dir = Path(args.wallet_dir).expanduser().resolve()
    account, created = initialize_wallet(wallet_dir)
    print(f"Wallet: {'CREATED' if created else 'REUSED'}")
    print(f"Base Sepolia address: {account.address}")
    print(f"Wallet files: {wallet_dir}")
    print("Network: Base Sepolia (chain ID 84532)")
    print("Explorer: https://sepolia.basescan.org/address/" + account.address)

    # Funding requires instructor credentials that are NOT copied into student repos.
    funder = get_funder(args.funder_wallet_dir)
    if funder and (created or args.top_up):
        if args.funder_wallet_dir and Path(args.funder_wallet_dir).resolve() == wallet_dir:
            raise ValueError("--funder-wallet-dir must be different from --wallet-dir")
        w3 = rpc_connection(args.rpc_url)
        print(f"Funding {args.grant_eth} Base Sepolia ETH from {funder.address} ...", flush=True)
        transfer_test_eth(w3, funder, account.address, args.grant_eth)
        print("Funding confirmed.")
    elif funder and not created:
        print("Existing wallet: no second grant sent. Use --top-up for an explicit additional grant.")
    else:
        print("No funding credentials supplied; wallet is ready to receive Base Sepolia test ETH.")
        print("To fund from your instructor wallet, use --funder-wallet-dir or FUNDER_PRIVATE_KEY.")
    print("BACK UP the complete wallet directory before deleting the Codespace.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
