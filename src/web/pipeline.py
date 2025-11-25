# src/web/pipeline.py
from preprocessing.features import extract_features
import numpy as np

def process_window(modality, window, fs):
    feats = extract_features(np.array(window).T, fs)  # adjust dims
    # run model -> label, prob
    return {"label":"...", "prob":0.5}
