#!/bin/bash
# Setup script for A100 Server (Ubuntu/Debian)

echo "Setting up Handwash Streaming Model on A100 Environment..."

# Update repos and install dependencies
sudo apt-get update
sudo apt-get install -y libgl1-mesa-glx python3-pip

# Install PyTorch with CUDA 12.1 optimizations for A100
echo "Installing PyTorch 2.1+ (CUDA 12.1)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install TensorRT and PyCUDA for Inference Engine
echo "Installing TensorRT & PyCUDA..."
pip install tensorrt tensorrt-cu12 pycuda onnx onnxruntime-gpu

# Install standard dependencies
echo "Installing other packages..."
pip install opencv-python mediapipe numpy scipy

echo "Setup Complete!"
echo "To export your train model to TensorRT engine (FP16 optimized), run:"
echo "python3 export_tensorrt.py --fp16"
