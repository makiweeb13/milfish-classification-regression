import os
import cv2
import numpy as np
import pandas as pd
from data.loader import load_yolo_dataset
import joblib
from utils.image_utils import (
    load_image,
    crop_roi,
    normalize_image,
    denoise_image,
    get_final_binary_mask,
    segment_fish_u2net
)
from utils.directories_utils import (
    train_images, train_labels, train_output,
    valid_images, valid_labels, valid_output,
    test_images, test_labels, test_output,
    size_train_data, size_valid_data, size_test_data,
    data_output, save_gradient_boosting_model, save_label_encoder, save_random_forest_model
)
from utils.extractor_utils import merge_features_with_csv
from sklearn.metrics import classification_report, accuracy_score

# Model imports
from models.gradient_boosting.train_gradient_boosting import classify_fish_with_gradient_boosting
from models.gradient_boosting.test_gradient_boosting import gradientBoostingClassifier

from models.random_forest.train_random_forest import classify_fish_with_random_forest
from models.random_forest.test_random_forest import randomForestClassifier

os.makedirs(train_output, exist_ok=True)
os.makedirs(valid_output, exist_ok=True)
os.makedirs(test_output, exist_ok=True)

def load_and_preprocess_train_images(df, image_path):

    for index, row in df.iterrows():
        image_path = os.path.join(train_images, row["image_id"] + ".jpg")

        # Load the full image
        img = load_image(image_path)
        if img is None:
            print(f"Could not load image {image_path}")
            continue

        # Crop the fish ROI
        crop = crop_roi(img, row["bbox_x"], row["bbox_y"], row["bbox_width"], row["bbox_height"])

        # Apply normalization, denoising, contrast enhancement
        crop = normalize_image(crop)
        crop = denoise_image(crop)
        # crop = enhance_contrast(crop)
        crop = get_final_binary_mask(crop)

        print(f"Processed {row['image_id']} fish {row['fish_id']} of class {row['mapped_class']}")

        # Save processed image crop
        save_path = os.path.join(
            train_output,
            f"{row['image_id']}_fish{row['fish_id']}_{row['mapped_class'].replace(' ', '')}.jpg"
        )
        cv2.imwrite(save_path, crop)

def extract_features():
    # Load YOLO dataset
    load_yolo_dataset(train_images, train_labels, f"{data_output}{size_train_data}")
    load_yolo_dataset(valid_images, valid_labels, f"{data_output}{size_valid_data}")
    load_yolo_dataset(test_images, test_labels, f"{data_output}{size_test_data}")

    # Preprocess and segment train_images
    print("Segmenting images...")
    segment_fish_u2net(train_images, train_output)
    segment_fish_u2net(valid_images, valid_output)
    segment_fish_u2net(test_images, test_output)

    # Extract features and merge with existing CSV
    print("Extracting features...")
    features_csv_path = f"{data_output}{size_train_data}"
    valid_features_csv_path = f"{data_output}{size_valid_data}"
    test_features_csv_path = f"{data_output}{size_test_data}"

    if not exists(features_csv_path) or not exists(valid_features_csv_path) or not exists(test_features_csv_path):
        return

    merge_features_with_csv(features_csv_path, train_output, features_csv_path)
    merge_features_with_csv(valid_features_csv_path, valid_output, valid_features_csv_path)
    merge_features_with_csv(test_features_csv_path, test_output, test_features_csv_path)  


def exists(path):
    if not os.path.exists(path):
        print(f"Directory {path} does not exist.")
        return False
    return True


def train_gradient_boosting():
    classify_fish_with_gradient_boosting()


def classify_gradient_boosting():
    gradientBoostingClassifier()

def train_random_forest():
    classify_fish_with_random_forest()

def classify_random_forest():
    randomForestClassifier()   

def ensemble_soft_voting():

    test_df = pd.read_csv(f"{data_output}{size_test_data}")

    X_test = test_df.drop(columns=["mapped_class"])
    y_test = test_df['mapped_class'] 
    
    le = joblib.load(save_label_encoder)
    y_test_encoded = le.transform(y_test)

    gb_model = joblib.load(save_gradient_boosting_model)
    rf_model = joblib.load(save_random_forest_model)

    gb_probs = gb_model.predict_proba(X_test)
    rf_probs = rf_model.predict_proba(X_test)

    avg_probs = (gb_probs + rf_probs) / 2
    
    ensemble_preds = np.argmax(avg_probs, axis=1)

    accuracy = accuracy_score(y_test_encoded, ensemble_preds)
    report = classification_report(y_test_encoded, ensemble_preds, target_names=le.classes_)

    print(f"Ensemble Test Accuracy: {accuracy:.4f}")
    print("Classification Report (Ensemble):")
    print(report)

