# Setup

## Installation of libmagic

### For macOS

On macOS, you can install libmagic using Homebrew:

```bash
brew install libmagic
```

### For Linux

Most Linux distributions provide libmagic through their package managers. For example, on Debian-based systems like Ubuntu, you can install it with:

```bash
sudo apt-get install libmagic1
```
### For Windows

On Windows, installing libmagic requires additional steps, as it is not natively available. To set it up:​

1. Install the python-magic-bin package, which includes the necessary libmagic binaries for Windows:

```bash
pip install python-magic-bin
```

This package provides the libmagic functionality tailored for Windows environments.

2. Ensure the libmagic DLLs are accessible:

The python-magic-bin package installs the required DLLs, but you may need to ensure they are in your system's PATH. Locate the libmagic DLLs within your Python environment, typically found in the Lib\site-packages\python_magic_bin directory. Add this path to your system's PATH environment variable if it's not already included.

3. Verify the installation:

After installation, you can verify that libmagic is working by running a simple test in Python:

```python
import magic

print(magic.from_buffer(b'#!/usr/bin/env python3\nprint("Hello, World!")', mime=True))
```

If configured correctly, this should output:

```arduino
text/x-script.python
```

By following these steps, you should have libmagic properly installed on your Windows system, enabling file type identification in your Python applications.​

## Packages
Python 3.13

You can install packages using "pip install -r requirements.txt" on the environment (conda or venv)

## Environment file

Settings in general are maintained by .env files. Refer to the following for the required configurations

```bash
OPENAI_API_KEY = "your open api key here"
PYTHONPATH = "."
BASE_URL = "base url when doing API calls to the LLM. Do not include this if not running LLMs through an URL"
MODEL = model used as a fallback
FINANCE_CLERK_MODEL = "model for the agent using the OCR tool"
SUPERVISOR_MODEL = "model for the supervisor agent"
SQL_MODEL = "model for the agents needed to write SQL"
VISION_BASE_URL = "base url when doing API calls to the LLM vision model. Do not include this if not running LLMs through an URL"
VISION_MODEL = "model for the OCR tool"
```

Sample here
```bash
OPENAI_API_KEY = "your open api key here""
BASE_URL = "http://localhost:12345"
PYTHONPATH = "."
MODEL = "gpt-4o-mini"
FINANCE_CLERK_MODEL = "gpt-4o-mini"
SUPERVISOR_MODEL = "gpt-4o-mini"
SQL_MODEL = "gpt-4o"
VISION_BASE_URL = "http://localhost:6789"
VISION_MODEL = "llava:7b"
```

## Installation of Ollama

Refer to: [Ollama README](https://github.com/ollama/ollama/blob/main/README.md)

### Pull Vision Model

```bash
ollama pull llama3.2-vision:11b
```

# Run
## Main script
Run the following script for the service
```bash
python app.py
```

## ReconApp

### Parameters
The following are the parameters for the ReconApp class

_Note_: the environment variable "MODEL"

| Parameter           | Type    | Description                                                            | Default                     |
| --------            | ------- | --------                                                               | -------                     |
| supervisor_model    | str     | LLM model for the supervisor                                           | env["SUPERVISOR_MODEL"]     | 
| sql_model           | str     | LLM model for the sql agents                                           | env["SQL_MODEL"]            |
| finance_clerk_model | str     | LLM model for the finance clerk (triggers the ocr tool)                | env["FINANCE_CLERK_MODEL"]  |
| vision_model        | str     | LLM vision model for the OCR tool                                      | env["VISION_MODEL"]         |
| max_retries         | int     | Max retries when the langgraph encounters an error                     | 3                           |
| batch_size          | int     | Batch size to query for the emails in the email database               | 10                          |
| tool_based          | bool    | Set to true if we want to use the sql query tool instead of SQL agents | False                       |
| reset_db_state      | bool    | If the database to run needs to be reset                               | False                       |

### Functions
``` python
# kick starts the process
def run(self, query: str = "SELECT * FROM emails"):
```

### Example usage

```python
ReconApp(
    supervisor_model = os.environ["SUPERVISOR_MODEL"],
    sql_model = os.environ["SQL_MODEL"],
    finance_clerk_model = os.environ["FINANCE_CLERK_MODEL"],
    vision_model = os.environ["VISION_MODEL"],
    max_retries = 3,
    batch_size = 10,
    tool_based=True,
    reset_db_state=True
).run()
```

## Evaluation Scripts

We provide convenient scripts to reproduce all results presented in the paper.

### Evaluating OpenAI Models

- Ensure that the `OPENAI_API_KEY` is correctly set in the `.env` file.
- Then, run the following scripts:

```bash
./scripts/eval-gpt.sh gpt-4o-mini
./scripts/eval-gpt.sh gpt-4o
```


### Evaluating Open-Source Models
- For GPUs with lower memory (e.g., RTX 4090 with 24GB VRAM), run:

```bash
./scripts/eval-rtx-4090.sh
```

- For GPUs with higher memory (e.g., RTX A6000 with 48GB VRAM), run:

```bash
./scripts/eval-rtx-a6000.sh
```

### Results

#### Databases
Databases will be created under folder src/data/db. The subfolder that it will be under will be the concatenation of "MODEL" and "VISION_MODEL" environment variables to prevent accidental replacement
of DBs for different runs

Each DB will be modeled after their respective CSVs

_Note_: Please make sure the headers are available as stated below if the CSV is recreated and store the csv with their respective names under src/data/synthetic_data

DB samples are under src/data/db/sample, where we ran the code for the first 10

1. Email

| Header              | Type | Description |
| ------              | ---- | ----------- |
| email_id            | str  | ID of emails in the database |
| sender_email        | str  | Email address of sender |
| recipient_email     | str  | Email address of recipient |
| subject             | str  | Subject of email |
| email_body          | str  | Body of email |
| filename            | str  | Filename of the attachments, empty if attachments does not exist |
| timestamp           | str  | Timestamp of email |
| process_status      | str  | Status of processing. NOT_STARTED = "not processed yet", NOT_INVOICE = "LLM deems the email is not related to invoices", ERROR = "Error encountered, i.e can't find invoice in the database", API_ERROR = "LLM api call error", RECURSION_LIMIT_REACHED = "Recursion limit set reached", SUCCESS = "Successfully reconciled"  |
| response            | str  | Final response text from the LLM |
| start_time          | str  | Start time of the process in ISO format                       |
| end_time            | str  | End time of the process in ISO format                         |
| full_logs           | str  | List of logs of the LLM exchanges in the request              |
| total_time          | str  | Total time taken to run the process                           |
| successful_requests | str  | Number of successful requests from the LLM                    |
| total_tokens        | str  | Total LLM tokens used                                         |
| prompt_tokens       | str  | Total LLM prompt tokens used                                  |
| completion_tokens   | str  | Total LLM completion tokens used                              |
| total_cost          | str  | Estimated total cost of the requests. Only applicable for OpenAI models |

The data under the following headers will be populated after the run:
- process_status
- response
- start_time
- end_time
- full_logs
- total_time
- successful_requests
- total_tokens
- prompt_tokens
- completion_tokens
- total_cost

An example of the logs
```json
{
    "name": "invoice_update_data_engineer",
    "type": "AIMessage",
    "content": "Tool calls to invoice_db_update_tool",
    "timestamp": "2025-01-08T16:43:30.448110",
    "usage": {
        "input_tokens": 213,
        "output_tokens": 91,
        "total_tokens": 304,
        "input_token_details": {
            "audio": 0,
            "cache_read": 0
        },
        "output_token_details": {
            "audio": 0,
            "reasoning": 0
        }
    },
    "model_name": "gpt-4o-2024-08-06",
    "additional_kwargs": {
        "tool_calls": [
            {
                "name": "invoice_db_update_tool",
                "args": {
                    "invoice_id": "43925",
                    "email_details": "Sender: RobinLevine@example.com\nSubject: Payment Confirmation for Invoice ID: 43925\nBody: Hi Tanya ! Please find attached payment screenshot for Invoice ID: 43925 , Regards Robin Levine\nAttachment: transaction_1.jpeg\nTime stamp: 2025-01-03T17:34:59.488354"
                },
                "id": "call_IsCDxKvGl9gIbILPyULgjZnD",
                "type": "tool_call"
            }
        ]
    }
}
```

2. Transactions

| Header               | Type | Description |
| ------               | ---- | ----------- |
| invoice_id           | str  | invoice ID  |
| bank_bane            | str  | Bank to pay the invoice to  |
| transaction_id       | str  | transaction ID |
| transaction_date     | str  | transaction date |
| amount               | str  | transaction amount |
| recipient_name       | str  | Person to make payment to |
| sender_name          | str  | Invoice pending collection from |
| reconciliation_state | str  | PAID or UNPAID     |
| email_details        | str  | the full email details used to reconcile this invoice |

The data under the following headers will be populated after the run:
- reconciliation_state
- email_details

#### Calculation and Visualization of Metrics

1. *Calculation of Metrics*

We’ve provided a Python script to calculate metrics from results stored under the src/data/db folder. Below is a sample run of the script:

```bash
$ python src/misc/calc_metrics.py src/data/db/RTX\ A6000 RTX\ A6000
Calculating metrics for directory: src/data/db/RTX A6000 for platform: RTX A6000 ...
Loading environment variables from: /Users/inflaton/code/papers/sme/.env
Calculating metrics for model: modelqwen2.5_7b...
Calculating metrics for model: modelfunctionary-small...
Calculating metrics for model: modelqwen2.5_32b...
Calculating metrics for model: modelfunctionary-medium...
Calculating metrics for model: modelqwen2.5_72b...
Metrics saved as src/data/db/metrics_RTX A6000.csv
```

2. *Visualization of Metrics* 

Open and execute the Jupyter notebook located at `notebooks/01_Data_Analysis_all_models.ipynb`. This notebook merges all the metrics files generated in the previous step and produces the plots included in the paper.
