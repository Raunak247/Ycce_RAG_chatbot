# -*- coding: utf-8 -*-
"""
Image embedding module using CLIP for multimodal FAISS ingestion.
- No local downloads
- In-memory processing
- Batch support
- Retry logic with timeout safety
"""

# ✅ REDIRECT ALL PATHS TO E DRIVE (C-drive protection)
import os
os.environ['TEMP'] = r'E:\temp'
os.environ['TMP'] = r'E:\temp'
os.environ['TMPDIR'] = r'E:\temp'
os.environ['PIP_CACHE_DIR'] = r'E:\.cache\pip'
os.environ['HUGGINGFACE_HUB_CACHE'] = r'E:\.cache\huggingface'
os.environ['HF_HOME'] = r'E:\.cache\huggingface'
os.environ['TORCH_HOME'] = r'E:\.cache\torch'
os.environ['TRANSFORMERS_CACHE'] = r'E:\.cache\transformers'
os.environ['KERAS_HOME'] = r'E:\.cache\keras'
os.environ['MPLCONFIGDIR'] = r'E:\.cache\matplotlib'
os.environ['NLTK_DATA'] = r'E:\.cache\nltk_data'
os.makedirs(r'E:\temp', exist_ok=True)
os.makedirs(r'E:\.cache\huggingface', exist_ok=True)

import torch
import requests
from typing import Optional, List
from PIL import Image
from io import BytesIO
from transformers import CLIPProcessor, CLIPModel


class ImageEmbedder:
    """CLIP-based image embedder for multimodal FAISS ingestion."""
    
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """Initialize CLIP model and processor."""
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = CLIPModel.from_pretrained(model_name)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            print(f"[ERROR] Failed to load CLIP model: {e}")
            raise
    
    def embed_image_from_url(self, url: str, retries: int = 2) -> Optional[List[float]]:
        """
        Fetch image from URL and generate embedding (NO local download).
        
        Args:
            url: Image URL
            retries: Max retry attempts
            
        Returns:
            Normalized embedding vector as list[float] or None on failure
        """
        for attempt in range(retries):
            try:
                # Fetch image in-memory
                response = requests.get(url, timeout=15, stream=True)
                response.raise_for_status()
                
                image = Image.open(BytesIO(response.content)).convert("RGB")
                
                # Generate embedding
                with torch.no_grad():
                    inputs = self.processor(images=image, return_tensors="pt")
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}
                    
                    # CLIP returns BaseModelOutputWithPooling with image_embeds
                    outputs = self.model.get_image_features(**inputs)
                    
                    # Extract embedding - outputs is a BaseModelOutputWithPooling
                    # which has image_embeds attribute (or we can access it as a tensor)
                    if hasattr(outputs, 'image_embeds'):
                        embedding_tensor = outputs.image_embeds
                    elif hasattr(outputs, 'last_hidden_state'):
                        embedding_tensor = outputs.last_hidden_state.mean(dim=1)
                    else:
                        # Direct tensor access
                        embedding_tensor = outputs
                    
                    # Convert to numpy and normalize
                    if isinstance(embedding_tensor, torch.Tensor):
                        embedding_np = embedding_tensor.cpu().detach().numpy()
                    else:
                        embedding_np = embedding_tensor
                        
                    if embedding_np.ndim > 1:
                        embedding_np = embedding_np[0]  # Take first sample if batch
                    embedding_np = embedding_np / (embedding_np**2).sum()**0.5
                    
                    return embedding_np.tolist()
                    
            except Exception as e:
                if attempt < retries - 1:
                    print(f"[RETRY] Image {attempt + 1}/{retries}: {url} - {type(e).__name__}")
                else:
                    print(f"[ERROR] Image embedding failed: {url} - {e}")
                continue
        
        return None

    def embed_image_from_path(self, image_path: str) -> Optional[List[float]]:
        """Generate embedding from a local cached image file path."""
        try:
            image = Image.open(image_path).convert("RGB")

            with torch.no_grad():
                inputs = self.processor(images=image, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                outputs = self.model.get_image_features(**inputs)

                if hasattr(outputs, 'image_embeds'):
                    embedding_tensor = outputs.image_embeds
                elif hasattr(outputs, 'last_hidden_state'):
                    embedding_tensor = outputs.last_hidden_state.mean(dim=1)
                else:
                    embedding_tensor = outputs

                if isinstance(embedding_tensor, torch.Tensor):
                    embedding_np = embedding_tensor.cpu().detach().numpy()
                else:
                    embedding_np = embedding_tensor

                if embedding_np.ndim > 1:
                    embedding_np = embedding_np[0]

                embedding_np = embedding_np / (embedding_np**2).sum()**0.5
                return embedding_np.tolist()
        except Exception as e:
            print(f"[ERROR] Local image embedding failed: {image_path} - {e}")
            return None
    
    def embed_images_batch(self, urls: List[str], batch_size: int = 32) -> dict:
        """
        Process multiple images in batches.
        
        Args:
            urls: List of image URLs
            batch_size: Batch processing size
            
        Returns:
            Dict with embeddings, skipped, and failed counts
        """
        results = {
            "embeddings": [],
            "urls": [],
            "skipped": 0,
            "failed": 0
        }
        
        for i, url in enumerate(urls):
            embedding = self.embed_image_from_url(url)
            if embedding is not None:
                results["embeddings"].append(embedding)
                results["urls"].append(url)
            else:
                results["failed"] += 1
            
            # Progress logging
            if (i + 1) % max(1, batch_size // 2) == 0:
                print(f"[IMG] Processed {i + 1}/{len(urls)} images")
        
        return results


# Global embedder instance
_image_embedder = None


def get_embedder() -> ImageEmbedder:
    """Get or create global image embedder."""
    global _image_embedder
    if _image_embedder is None:
        _image_embedder = ImageEmbedder()
    return _image_embedder


def embed_image_from_url(url: str) -> Optional[List[float]]:
    """
    Convenient function to embed single image URL.
    
    Args:
        url: Image URL
        
    Returns:
        Embedding vector or None
    """
    embedder = get_embedder()
    return embedder.embed_image_from_url(url)


def embed_image_from_path(image_path: str) -> Optional[List[float]]:
    """Convenient function to embed a local cached image file."""
    embedder = get_embedder()
    return embedder.embed_image_from_path(image_path)
