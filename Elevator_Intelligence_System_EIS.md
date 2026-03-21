# Elevator Intelligence System (EIS)

## Overview
This system analyzes locally stored elevator videos/images using AI and recommends the optimal elevator manufacturer based on user-defined use cases.

The system is fully offline and designed for accessibility (low vision + screen reader users).

---

## Core Architecture

UI Layer (wxPython)
    ↓
Application Layer (Controller)
    ↓
Recommendation Engine
    ↓
AI Engine (Image Classification)
    ↓
Local Data (Images / DB)

---

## AI Design

### Learning Strategy
Transfer Learning (pre-trained model + fine-tuning)

### Model Architecture
Input Image
    ↓
Feature Extractor (Pre-trained CNN)
    ↓
Custom Classifier Layer
    ↓
Output: Manufacturer Probability

---

## Dataset Design

### Data Sources
- Primary: User local videos/images
- Secondary: External images (optional)

### Data Generation
Video → Frame Extraction → Images → Manual Labeling

### Directory Structure
dataset/
 ├ train/
 │   ├ mitsubishi/
 │   ├ hitachi/
 │   ├ otis/
 ├ val/
 ├ test/

---

## Training Process

- Load pre-trained model
- Replace final layer
- Freeze base layers
- Train classifier layer
- Save model

---

## Inference Process

Video
 ↓
Frame Extraction
 ↓
Prediction per Frame
 ↓
Aggregation
 ↓
Final Manufacturer

---

## AI Engine

class AIEngine:
    def __init__(self):
        self.model = load_model()

    def predict_image(self, image):
        return predict(image)

    def predict_video(self, video):
        frames = extract_frames(video)
        results = [self.predict_image(f) for f in frames]
        return aggregate(results)

---

## Recommendation Engine

AI → classification
Recommendation → decision

score = w1*safety + w2*noise + w3*speed

---

## UI Integration

User Input
 ↓
Controller
 ↓
AI Engine
 ↓
Recommendation Engine
 ↓
UI Display + Voice Feedback

---

## Accessibility

- High contrast UI
- Large font
- Keyboard navigation
- Screen reader support

---

## Performance

- Image inference: 0.1–1 sec
- Video analysis: 10–30 sec
- Offline operation

---

## Summary

AI = Classification  
Recommendation = Decision  
UI = Communication  

System = AI + Knowledge + Accessible UI
