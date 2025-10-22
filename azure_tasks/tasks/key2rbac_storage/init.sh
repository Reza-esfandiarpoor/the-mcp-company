set -e
terraform init --upgrade
terraform apply -auto-approve

if [[ -z "${AZTASK_PYTHON_CMD}" ]]; then
    AZTASK_PYTHON_CMD='python3'
fi

# Install dependencies with platform restrictions
cd function_code
$AZTASK_PYTHON_CMD -m pip install \
  --target=".python_packages/lib/site-packages" \
  --platform manylinux2014_x86_64 \
  --only-binary=:all: \
  --python-version 3.9 \
  -r requirements.txt

# Create deployment package with dependencies
zip -r ../deploy.zip . -x "*.pyc" -x "__pycache__/*"
cd ..

# Deploy without triggering build
az functionapp deployment source config-zip \
  --resource-group azuretasks_key2rbac \
  --name pyfunc-blob-demorz2 \
  --src deploy.zip

# Clean up
rm deploy.zip || true


if [[ -f "function_code.zip" ]]; then
    rm "function_code.zip" || true
fi
