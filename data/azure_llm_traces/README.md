# Azure LLM inference traces (aggregated)

These files are 30-second aggregates of the public Azure LLM inference traces
from the [Azure Public Dataset](https://github.com/Azure/AzurePublicDataset),
which is released under the Creative Commons Attribution 4.0 (CC-BY 4.0) license.
Only per-bin counts are stored here; no per-request records are included.

| File | Source trace |
|---|---|
| `conv.csv` | Azure LLM inference trace 2023, conversation service (`AzureLLMInferenceTrace_conv.csv`) |
| `code.csv` | Azure LLM inference trace 2023, code service (`AzureLLMInferenceTrace_code.csv`) |
| `conv_1week.csv` | Azure LLM inference trace 2024, conversation service, one week (`AzureLLMInferenceTrace_conv_1week.csv`) |
| `code_1week.csv` | Azure LLM inference trace 2024, code service, one week (`AzureLLMInferenceTrace_code_1week.csv`) |

Columns:

- `bin`: index of the 30 s bin, counted from midnight of the first day of the trace
- `requests`: number of requests that arrived in the bin
- `gen_tokens`, `ctx_tokens`: total generated (output) and context (input) tokens in the bin
- `t0`: midnight of the first day of the trace

To rebuild them from the original traces, download the CSV files from the Azure
Public Dataset (see `AzureLLMInferenceDataset2023.md` and
`AzureLLMInferenceDataset2024.md` in that repository) and run, for example:

```bash
python experiments/08_trace_prepare.py /path/to/AzureLLMInferenceTrace_conv_1week.csv conv_1week
```

If you use these traces, please cite the papers listed by the Azure Public
Dataset for the 2023 and 2024 LLM inference traces.
