# Training Methodology

## Dataset Selection
I opted for a large-scale training corpus comprising over 100,000 video clips representing real, high-resolution faces and maliciously generated synthetics across various modalities (Faceswaps, Neural rendering, and latent manipulation). The dataset was selected due to its wide distribution of lighting conditions, varying degrees of compression artifacts, and cross-demographic variances. This heterogeneity is essential to force the CNN backbone to learn facial feature discrepancies rather than overfit on simple artifacts natively found in homogeneous datasets.

## Preprocessing Pipeline
To guarantee absolute symmetry between the training structure and the final live production inference system, I structured the preprocessing methodology into three isolated steps:
1. **Frame Extraction**: Linearly spaced segments are polled across the video duration.
2. **Face Bounding Box Detection**: I employed MTCNN configured with aggressive confidence thresholds to locate and tightly crop face boundaries. During training, I utilized half-resolution downscaling prior to face extraction—saving critical memory bottlenecks—while algorithmically mapping box coordinates back to full resolution to maintain image integrity.
3. **Isotropic Normalization**: Instead of brutally squashing face crops into a 380x380 square, I built an isotropic resize engine padded heavily to the center matrix. By doing this, we guarantee the facial aspect ratio is protected. Finally, standard ImageNet Mean `[0.485, 0.456, 0.406]` & Standard Deviation `[0.229, 0.224, 0.225]` distributions were applied.

## Model Selection
I evaluated multiple CNN architectures, eventually settling exclusively on the **EfficientNet B7** backbone. Unlike ResNet or older inception networks which scale vertically into diminishing returns, I leveraged the B7 structure because it mathematically optimizes network depth, width, and input resolution symmetrically. Deepfakes frequently introduce pixel-level bleeding along temporal mask edges; therefore, ingesting large 380x380 images is the only way a CNN can reliably spot these localized sub-pixel imperfections. The architecture consists of the feature extractor passed sequentially into a Global Average Pool and finally terminating in a Sigmoid prediction layer.

## Training Configuration
The hyperparameter strategy was mapped specifically around stability and regularization:
- **Optimizer**: AdamW was deployed, factoring decoupled weight decay mechanisms.
- **Batch Size**: Restricted to prevent extreme local minima jumps, averaging 32 frames across the sequence.
- **Epochs**: Training extended for 30 epochs, monitoring validation loss for early stopping to circumvent catastrophic overfitting on fake geometries.
- **Learning Rate**: A cosine-annealing loop was utilized, starting from 1e-3 and smoothly degrading.

## Evaluation
I implemented rigorous validation loops. The core benchmark targets were F1 metrics balancing Precision (trapping complex fakes) against Recall (not triggering false flags on real humans). Validated test curves generated validation scores pushing sub `0.166` Binary Cross Entropy configurations.

## Engineering Challenges Resolved
- **Train/Inference Distribution Misalignment**: Mid-project evaluations proved the model output highly unstable probabilities randomly biased toward `FAKE`. After performing an exhaustive parameter sweep, I discovered the root cause was an RGB/BGR inversion bug alongside MTCNN margin thresholds not aligning linearly to the pipeline. Engineering these to mathematically match normalized bounds stabilized the classification curve back down to `<10%` baseline failure.
