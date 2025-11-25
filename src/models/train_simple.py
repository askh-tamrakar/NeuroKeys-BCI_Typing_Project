# train_simple.py
import joblib, os, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from preprocessing.features import extract_features

DATA_DIR = "./data/processed/windows"  # populate this from record_session + manual labels

def load_dataset(data_dir, fs=250):
    X, y = [], []
    for f in os.listdir(data_dir):
        if not f.endswith(".npz"): continue
        dd = np.load(os.path.join(data_dir, f), allow_pickle=True)
        arr = dd["data"]
        label = dd.get("label")
        if label is None: continue
        feats = extract_features(arr, fs)
        X.append(feats); y.append(str(label))
    return np.vstack(X), np.array(y)

def run_train(out_path="./models/simple_rf.joblib"):
    X,y = load_dataset(DATA_DIR)
    X_train, X_test, y_train, y_test = train_test_split(X,y,test_size=0.2, random_state=42, stratify=y)
    clf = RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=42)
    clf.fit(X_train,y_train)
    print("test acc", clf.score(X_test,y_test))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump(clf, out_path)
