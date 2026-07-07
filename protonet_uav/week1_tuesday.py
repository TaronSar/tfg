import onnxruntime as ort
import numpy as np
import os

def verify_onnx_graph():
    model_path = "test_backbone.onnx"
    
    if not os.path.exists(model_path):
        print(f"[-] Error: Could not find '{model_path}' in the current directory.")
        return

    print(f"[+] Found '{model_path}'. Initializing ONNX Runtime Session...")
    
    # 1. Create an inference session targeting your local CPU
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
    
    # 2. Inspect the expected input layer properties
    input_meta = session.get_inputs()[0]
    input_name = input_meta.name
    input_shape = input_meta.shape
    
    # 3. Inspect the output embedding layer properties
    output_meta = session.get_outputs()[0]
    output_name = output_meta.name
    output_shape = output_meta.shape
    
    print("\n================ Graph Metadata ================")
    print(f"Input Node Layer Name : '{input_name}'")
    print(f"Expected Input Shape  : {input_shape} (Batch, Channels, Height, Width)")
    print(f"Output Node Layer Name: '{output_name}'")
    print(f"Output Embedding Shape: {output_shape} (Batch, Channels, Height, Width)")
    print("================================================\n")

    # 4. Generate a random mock image matching the dimensions (1, 3, 224, 224)
    # Using float32 to match standard neural network weights
    print("[+] Generating random 224x224 mock crop tensor...")
    mock_crop = np.random.randn(1, 3, 224, 224).astype(np.float32)
    
    # 5. Run a local forward execution pass
    print("[+] Executing forward pass through the ONNX backbone...")
    raw_output = session.run([output_name], {input_name: mock_crop})
    embedding_vector = raw_output[0]
    
    print("\n[+] Success! Inference run finished without exceptions.")
    print(f"[+] Resulting feature vector spatial dimension: {embedding_vector.shape}")
    
    # Check if it needs dynamic pooling adjustment later
    if len(embedding_vector.shape) == 4:
        # Standard MobileNet feature extractors often return [1, 576, 7, 7] or similar feature maps
        print("[Note] Output is a 4D feature map tensor. In our Prototypical training loop,")
        print("       we will pass this through an Average Pooling layer to get a clean 1D embedding array.")

if __name__ == "__main__":
    verify_onnx_graph()