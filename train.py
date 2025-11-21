import pandas as pd
import joblib
from sklearn.preprocessing import MultiLabelBinarizer, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# File names
SYMPTOM_FILE = "DiseaseAndSymptoms.csv"
PRECAUTION_FILE = "Disease precaution.csv"

# 1. Load datasets
df = pd.read_csv(SYMPTOM_FILE)
precaution_df = pd.read_csv(PRECAUTION_FILE)

df.fillna("", inplace=True)
precaution_df.fillna("", inplace=True)

# 2. Process symptoms
symptom_cols = [col for col in df.columns if col.lower().startswith("symptom")]
if symptom_cols:
    df["all_symptoms"] = df[symptom_cols].apply(
        lambda x: [s for s in x if s != ""], axis=1
    )
elif "Symptoms" in df.columns:
    df["all_symptoms"] = df["Symptoms"].apply(
        lambda x: [s.strip() for s in str(x).split(",") if s.strip()]
    )
else:
    raise ValueError("⚠ No symptom columns found in dataset!")

# 3. One-hot encode symptoms
mlb = MultiLabelBinarizer()
X = mlb.fit_transform(df["all_symptoms"])

# 4. Encode diseases
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(df["Disease"])

# 5. Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 6. Train model
model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X_train, y_train)

# 7. Evaluate accuracy
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"✅ Model trained successfully! Accuracy: {accuracy:.2f}")

# 8. Create disease-to-precaution mapping
disease_precautions = {}
for _, row in precaution_df.iterrows():
    precautions = [row[col] for col in precaution_df.columns if col.lower().startswith("precaution") and row[col] != ""]
    disease_precautions[row["Disease"]] = precautions

# 9. Save everything in one file
data_bundle = {
    "model": model,
    "mlb": mlb,
    "label_encoder": label_encoder,
    "disease_precautions": disease_precautions
}

joblib.dump(data_bundle, "disease_prediction_bundle.pkl")
print("🎉 Model, encoders, and precautions saved to disease_prediction_bundle.pkl")