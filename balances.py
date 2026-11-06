#!/usr/bin/env python3
"""Print Base Sepolia ETH, Circle test USDC, and optional team ERC-20 balance."""

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

from web3 import Web3

CHAIN_ID = 84532
DEFAULT_RPC = "https://sepolia.base.org"
# Circle's TEST USDC on BASE SEPOLIA; not Base mainnet USDC.
USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

ERC20_ABI = [
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
]


def display_amount(raw: int, decimals: int) -> str:
    return format(Decimal(raw) / (Decimal(10) ** decimals), "f")


def token_balance(w3: Web3, token_address: str, owner: str, name_fallback: str):
    token = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
    raw = token.functions.balanceOf(owner).call()
    decimals = token.functions.decimals().call()
    try:
        symbol = token.functions.symbol().call()
    except Exception:
        symbol = name_fallback
    return symbol, display_amount(raw, decimals)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet-dir", default="wallet", help="Directory containing address.txt")
    parser.add_argument(
        "--token-address", default=os.getenv("TEAM_TOKEN_ADDRESS", ""),
        help="Team ERC-20 contract address; alternatively set TEAM_TOKEN_ADDRESS"
    )
    parser.add_argument("--rpc-url", default=os.getenv("BASE_SEPOLIA_RPC_URL", DEFAULT_RPC))
    args = parser.parse_args()

    address_file = Path(args.wallet_dir).expanduser() / "address.txt"
    if not address_file.is_file():
        raise FileNotFoundError(f"No {address_file}. Run create_wallet.py first.")
    address = Web3.to_checksum_address(address_file.read_text(encoding="utf-8").strip())
    w3 = Web3(Web3.HTTPProvider(args.rpc_url, request_kwargs={"timeout": 25}))
    if not w3.is_connected():
        raise RuntimeError(f"Unable to connect to RPC: {args.rpc_url}")
    if w3.eth.chain_id != CHAIN_ID:
        raise RuntimeError(f"Wrong chain ID {w3.eth.chain_id}; expected {CHAIN_ID}")

    print("Network: Base Sepolia (84532)")
    print(f"Wallet address: {address}")
    print(f"Base Sepolia ETH: {display_amount(w3.eth.get_balance(address), 18)}")
    symbol, amount = token_balance(w3, USDC_ADDRESS, address, "USDC")
    print(f"Base Sepolia test {symbol}: {amount}")
    if args.token_address:
        symbol, amount = token_balance(w3, args.token_address, address, "TEAM")
        print(f"Team token ({symbol}): {amount}")
        print(f"Team token contract: {Web3.to_checksum_address(args.token_address)}")
    else:
        print("Team token: not configured (pass --token-address 0x... after Remix deployment)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
