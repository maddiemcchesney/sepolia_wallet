# Portable Base Sepolia wallet (no LLM, no GUI)

These two Python commands work independently of any chatbot, registry, or Codespace.
An Ethereum wallet address is determined by its private key, not by its host.
**Only Base Sepolia (chain ID 84532) is used for transactions and balances.**

## Install

```bash
python -m pip install -r requirements.txt
```

## Create a new wallet

```bash
python create_wallet.py
```

This creates `wallet/keystore.json`, `wallet/.password`, and `wallet/address.txt`,
then prints the public address for use in Remix. Re-running the command **reuses**
the same account. Wallet files are ignored by `.gitignore`.

**Back up all three wallet files separately, outside the Git repo.** Never
publish them in a GitHub repository or class ZIP. A new Codespace without the
files will create a different address.

## Fund it from your instructor's EXISTING Base Sepolia wallet

If you run the command in an environment where your instructor wallet directory
is available, specify its path. Example (the instructor's wallet is in `wallet/`
and the newly created portable wallet will be in `wallets/team-a/`):

```bash
python create_wallet.py --wallet-dir wallets/team-a --funder-wallet-dir wallet --grant-eth 0.0001
```

The script decrypts the instructor's local keystore, signs a **Base Sepolia ETH**
transfer, broadcasts it, and waits for confirmation. It prints the tx hash.
The instructor wallet's password must be in its `.password` file, or set
`FUNDER_WALLET_PASSWORD` in the environment.

**Alternatively**, in an instructor-controlled Codespace, store the instructor
private key as a **Codespaces secret** named `FUNDER_PRIVATE_KEY`, then run:

```bash
python create_wallet.py --wallet-dir wallets/team-a --grant-eth 0.0001
```

**Do not put `FUNDER_PRIVATE_KEY`, an instructor keystore, or its password in a
repository you distribute to students.** A student Codespace without instructor
credentials will still create a wallet; it just cannot autonomously debit your
instructor wallet. You can later fund its printed address from your instructor
wallet or existing registry funding service.

For an already-created wallet, funding will **not** repeat by default. To make
an intentional additional grant, pass `--top-up` along with funding credentials:

```bash
python create_wallet.py --wallet-dir wallets/team-a --funder-wallet-dir wallet --grant-eth 0.0001 --top-up
```

## Print balances

```bash
python balances.py
```

For a wallet in a non-default folder:

```bash
python balances.py --wallet-dir wallets/team-a
```

After deploying your team ERC-20 token in Remix:

```bash
python balances.py --wallet-dir wallets/team-a --token-address 0xYOUR_TEAM_ERC20_CONTRACT
```

Or set the `TEAM_TOKEN_ADDRESS` environment variable to the deployed contract
address and simply run `python balances.py`.

The balance command prints native Base Sepolia ETH, **Circle's Base Sepolia test
USDC** (contract `0x036CbD53842c5426634e7929541eC2318f3dCF7e`), and the
team token, using each token's `decimals()` and `symbol()`.

## Moving the wallet into a new agent

Copy the complete `wallet/` directory to the new application's `wallet/`
directory. Run `python create_wallet.py` to verify it reuses the original
address. Update the agent's configuration so its wallet code points to that
directory. Wallet balances remain on-chain and will be readable from the new
agent; neither the agent code nor the Git repository stores them.

## RPC settings

Default: `https://sepolia.base.org` (Base Sepolia chain 84532).
If needed, configure `BASE_SEPOLIA_RPC_URL` with an alternative Base Sepolia
RPC endpoint. The scripts reject an endpoint reporting a different chain ID.

## Note on security

The generated encrypted keystore and its password are stored together in the
wallet folder for ease of portability in this testnet teaching exercise. This
is **not** a recommended arrangement for wallets holding real assets.
