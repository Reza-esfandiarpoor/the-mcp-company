# Azure Tasks

<p align="center"><img alt="Sample Azure task" src="https://huggingface.co/datasets/BatsResearch/themcpcompany_artifacts/resolve/main/azt.png"/></p>

To run the Azure tasks, you need to create a free account and a service principle and configure two command line tools.
Follow the instructions below to set up the environment.

## Azure Account

Follow these steps to create the account and service principle.

#### Create a free Azure account

Sign up for a free Azure account [here](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account).

#### Create a subscription

Create a subscription (if not exists already). You will need the subscription ID later.

#### Create a service principle

Refer to the [Official guide](https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal#register-an-application-with-microsoft-entra-id-and-create-a-service-principal) or follow these steps:

- Go to [portal.azure.com](https://portal.azure.com)
- Search for and go to `Microsoft Entra ID` page
- Expand `Manage` from the left menu
- Choose `App registrations`
- Click `New registration`
- Choose a name and use default values for other fields and click `Register`
- Once the service principle is created, save the value of `Directory (tenant) ID` and `Application (client) ID`.
- Click `Add a certificate or secret` and then `New client secret`
- Choose a name and click `add` and save the value of the new secret

#### Give owner access to the service principle

- Go to the target subscription
- Choose `Access control (IAM)`
- Click `Add` and then `Add role assignment`
- Go to `Privileged administrator roles` and choose `owner` from the list and click next
- Click `Select members` and search for the name of the service principle you just created and click `select`
- Choose the second option for 'what user can do' (i.e., `Allow user to assign all roles except privileged administrator roles Owner, UAA, RBAC (Recommended)`)
- Click `next`
- Click `Review + assign`

#### Create credentials file

Create `azure_tasks/azure_creds.sh` with the following content (use the values from above steps)

```bash
export AZTASK_SUBSCRIPTION_ID='Subscription id'
export AZURE_TENANT_ID='Directory (tenant) id'
export AZURE_CLIENT_ID='Application (client) id'
export AZURE_CLIENT_SECRET='value of service principle secret'
```

## CLI Tools

Some tasks use `az` and `azd` CLI tools.
Follow the official instructions for installing [az](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) and [azd](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-linux) commands.

### Isolating Accounts (Optional)

If you are already using `az` and `azd` commands with a different subscription on your machine, you can isolate your main account from the account for these experiments.
Basically, hiding your existing subscription from both the agent and init/cleanup scripts.

First, create two directories that save `az` and `azd` configuration files for your test account. Then, create this script (`azure_tasks/isolated_azure_tools.sh`) with the following content:

```bash
export AZURE_CONFIG_DIR='/path/to/dir/for/az/cli/config'
export AZD_CONFIG_DIR='/path/to/dir/for/azd/dev/config'
```


### Login

If you followed the steps for isolating your existing subscriptions, first run `source azure_tasks/isolated_azure_tools.sh` before proceeding.

Follow the official guides ([az](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest) and [azd](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd?tabs=winget-windows%2Cbrew-mac%2Cscript-linux&pivots=os-linux)) and log in with the account and subscription created above.

**Important**: If you want the isolation, you should login from the same shell session that you run `source azure_tasks/isolated_azure_tools.sh` from.
