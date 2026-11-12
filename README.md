# Optiland challenges evaluator

This repository scores the lens designs submitted to the
[Optiland challenges](https://www.optiland.org/competitions). The official
judge runs this code, and you can run the same code on your computer to check
a design before you submit it.

## Check a design

Save your lens from Optiland:

```python
from optiland.fileio import save_optiland_file

save_optiland_file(lens, "my_lens.json")
```

Then evaluate it:

```bash
git clone https://github.com/optiland/challenges-eval
cd challenges-eval
python -m pip install -r requirements.txt
python challenge_evaluator.py my_lens.json --challenge rms
```

The `--challenge` value names the challenge (for example `rms`, `doublet` or
`wide_angle`). The command writes a JSON report with the status, the score
(lower is better) and, if the design fails, the reasons.

You can also call it from Python:

```python
from challenge_evaluator import evaluate_design

report = evaluate_design(lens_file_data, challenge="rms")
print(report["status"], report["score"], report["violations"])
```

Use a separate Python environment. Results are official only in the pinned
environment of `requirements.txt`; elsewhere you get an `unofficial_score`.

## Where to find the details

| What | Where |
|---|---|
| Rules, requirements and score of each challenge | [RULES.md](RULES.md) |
| Reference designs and their scores | [examples/](examples/) |
| How the official judge runs | [judge/README.md](judge/README.md) |
| Why the rules are as they are, known limits | [docs/background.md](docs/background.md) |
| Test and validation results | [validation/VALIDATION.md](validation/VALIDATION.md) |

## Tests

```bash
python -m pytest -q tests
```

## License

MIT, see [LICENSE](LICENSE). The reference designs derive from Optiland
samples; the Optiland license is in [OPTILAND_LICENSE.txt](OPTILAND_LICENSE.txt).
