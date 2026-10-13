# Publishing on Kaggle

`cut-that-doesnt-travel.ipynb` is the public code notebook the competition requires. It is generated from this
repository by `python scripts/build_kaggle_notebook.py`, so rebuild it after any code change. It writes the project's
`src/` and `notebooks/` files, runs all six steps on Kaggle's copy of the competition data (about 15–20 minutes on
CPU), and shows the writeup's tables and figures.

Kaggle's menu names change from time to time; if a name below doesn't match, look for the closest one.

## 1. Publish the notebook (about 25 minutes, mostly waiting)

1. Open the NFL Big Data Bowl 2027 competition page, go to **Code**, and click **New Notebook**. Starting from the
   competition page attaches the competition data automatically.
2. In the notebook editor, use **File → Import Notebook** and upload `kaggle/cut-that-doesnt-travel.ipynb`.
3. Check that the **Input** panel lists the competition data. If it doesn't, add it with **Add Input**.
4. Click **Save Version**, choose **Save & Run All**, and wait for the run to finish (15–20 minutes). The run log
   should end with all six steps printed and no errors.
5. Open the saved version, click **Share**, and set it to **Public**.

## 2. Submit the writeup

1. On the competition page, start a new **Writeup**.
2. Paste the text of `writeup/writeup.md`.
3. Upload the six figures from `reports/figures/` and put each one where its `![...](...)` line is:
   `04_signature.png`, `03_tests.png`, `04_within.png`, `04_ceiling.png`, `04_card.png`, `04_stabilize.png`.
4. Attach the public notebook from step 1.
5. Choose the track (Open, or University if every team member is an undergraduate) and submit before
   **January 6, 2027, 11:59 PM UTC**.
