from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import torch
import torchvision
from torchvision import transforms, models
from torch.utils.data import DataLoader
from torch.utils.data.dataset import Dataset
import os
import numpy as np
import cv2
import threading
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    import face_recognition
except ImportError:
    face_recognition = None
from torch.autograd import Variable
import time
import sys
from torch import nn
import json
import glob
import copy
from torchvision import models
import shutil
from PIL import Image as pImage
import time
from django.conf import settings
from .forms import VideoUploadForm

index_template_name = 'index.html'
predict_template_name = 'predict.html'
about_template_name = "about.html"

# Ensure required folders exist (models, uploads, etc.)
required_dirs = [
    os.path.join(settings.PROJECT_DIR, 'models'),
    os.path.join(settings.PROJECT_DIR, 'uploaded_images'),
    os.path.join(settings.PROJECT_DIR, 'uploaded_videos'),
]
for _dir in required_dirs:
    os.makedirs(_dir, exist_ok=True)

im_size = 112
mean=[0.485, 0.456, 0.406]
std=[0.229, 0.224, 0.225]
sm = nn.Softmax(dim=1)
inv_normalize =  transforms.Normalize(mean=-1*np.divide(mean,std),std=np.divide([1,1,1],std))
# Use a proper torch.device so tensors and model are always on the same device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

train_transforms = transforms.Compose([
                                        transforms.ToPILImage(),
                                        transforms.Resize((im_size,im_size)),
                                        transforms.ToTensor(),
                                        transforms.Normalize(mean,std)])

class Model(nn.Module):

    def __init__(self, num_classes,latent_dim= 2048, lstm_layers=1 , hidden_dim = 2048, bidirectional = False):
        super(Model, self).__init__()
        model = models.resnext50_32x4d(pretrained = True)
        self.model = nn.Sequential(*list(model.children())[:-2])
        self.lstm = nn.LSTM(latent_dim,hidden_dim, lstm_layers,  bidirectional)
        self.relu = nn.LeakyReLU()
        self.dp = nn.Dropout(0.4)
        # LSTM output dim depends on bidirectionality
        lstm_out_dim = hidden_dim * (2 if bidirectional else 1)
        self.linear1 = nn.Linear(lstm_out_dim, num_classes)
        self.avgpool = nn.AdaptiveAvgPool2d(1)

    def forward(self, x):
        batch_size,seq_length, c, h, w = x.shape
        x = x.view(batch_size * seq_length, c, h, w)
        fmap = self.model(x)
        x = self.avgpool(fmap)
        # avgpool -> (batch*seq, channels, 1, 1)
        channels = x.shape[1]
        x = x.view(batch_size,seq_length,channels)
        x_lstm,_ = self.lstm(x,None)
        return fmap,self.dp(self.linear1(x_lstm[:,-1,:]))


class validation_dataset(Dataset):
    def __init__(self,video_names,sequence_length=60,transform = None):
        self.video_names = video_names
        self.transform = transform
        self.count = sequence_length

    def __len__(self):
        return len(self.video_names)

    def __getitem__(self,idx):
        if face_recognition is None:
            raise RuntimeError("face_recognition library is not installed. Install dependencies to enable face cropping.")
        video_path = self.video_names[idx]
        frames = []
        a = int(100/self.count)
        first_frame = np.random.randint(0,a)
        for i,frame in enumerate(self.frame_extract(video_path)):
            #if(i % a == first_frame):
            # OpenCV gives BGR, but face_recognition expects RGB.
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face_recognition.face_locations(rgb_frame)
            if faces:
                top, right, bottom, left = faces[0]
                # Crop using the original frame coordinates
                frame = frame[top:bottom, left:right, :]
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(self.transform(rgb_frame))
            if(len(frames) == self.count):
                break
        """
        for i,frame in enumerate(self.frame_extract(video_path)):
            if(i % a == first_frame):
                frames.append(self.transform(frame))
        """        
        # if(len(frames)<self.count):
        #   for i in range(self.count-len(frames)):
        #         frames.append(self.transform(frame))
        #print("no of frames", self.count)
        if len(frames) == 0:
            raise ValueError(f"No frames extracted from video: {video_path}")

        # If the video has fewer frames than requested, pad by repeating the last frame.
        # This prevents torch.stack([]) and keeps the input shape stable for the model.
        if len(frames) < self.count:
            last = frames[-1]
            while len(frames) < self.count:
                frames.append(last.clone())

        frames = torch.stack(frames[:self.count])
        return frames.unsqueeze(0)
    
    def frame_extract(self,path):
      vidObj = cv2.VideoCapture(path) 
      success = 1
      while success:
          success, image = vidObj.read()
          if success:
              yield image

def im_convert(tensor, video_file_name):
    """ Display a tensor as an image. """
    image = tensor.to("cpu").clone().detach()
    image = image.squeeze()
    image = inv_normalize(image)
    image = image.numpy()
    image = image.transpose(1,2,0)
    image = image.clip(0, 1)
    # This image is not used
    # cv2.imwrite(os.path.join(settings.PROJECT_DIR, 'uploaded_images', video_file_name+'_convert_2.png'),image*255)
    return image

def im_plot(tensor):
    if plt is None:
        return
    image = tensor.cpu().numpy().transpose(1,2,0)
    b,g,r = cv2.split(image)
    image = cv2.merge((r,g,b))
    image = image*[0.22803, 0.22145, 0.216989] +  [0.43216, 0.394666, 0.37645]
    image = image*255.0
    plt.imshow(image.astype('uint8'))
    plt.show()


def predict(model,img,path = './', video_file_name=""):
  with torch.no_grad():
    _,logits = model(img.to(device))
  logits = sm(logits)
  _,prediction = torch.max(logits,1)
  confidence = logits[:,int(prediction.item())].item()*100
  print('confidence of prediction:',confidence)
  return [int(prediction.item()),confidence]

def plot_heat_map(i, model, img, path = './', video_file_name=''):
  fmap,logits = model(img.to(device))
  params = list(model.parameters())
  weight_softmax = model.linear1.weight.detach().cpu().numpy()
  logits = sm(logits)
  _,prediction = torch.max(logits,1)
  idx = np.argmax(logits.detach().cpu().numpy())
  bz, nc, h, w = fmap.shape
  #out = np.dot(fmap[-1].detach().cpu().numpy().reshape((nc, h*w)).T,weight_softmax[idx,:].T)
  out = np.dot(fmap[i].detach().cpu().numpy().reshape((nc, h*w)).T,weight_softmax[idx,:].T)
  predict = out.reshape(h,w)
  predict = predict - np.min(predict)
  predict_img = predict / np.max(predict)
  predict_img = np.uint8(255*predict_img)
  out = cv2.resize(predict_img, (im_size,im_size))
  heatmap = cv2.applyColorMap(out, cv2.COLORMAP_JET)
  img = im_convert(img[:,-1,:,:,:], video_file_name)
  result = heatmap * 0.5 + img*0.8*255
  # Saving heatmap - Start
  heatmap_name = video_file_name+"_heatmap_"+str(i)+".png"
  image_name = os.path.join(settings.PROJECT_DIR, 'uploaded_images', heatmap_name)
  cv2.imwrite(image_name,result)
  # Saving heatmap - End
  result1 = heatmap * 0.5/255 + img*0.8
  r,g,b = cv2.split(result1)
  result1 = cv2.merge((r,g,b))
  return image_name

# Model Selection
def get_accurate_model(sequence_length):
    """Return the model filename that best matches the requested sequence_length.

    Filename format expected: <something>_<something>_<something>_<sequence>_<...>.pt (e.g. model_84_acc_10_frames_final_data.pt)
    If no matching model is found, returns an empty string.
    """

    list_models = glob.glob(os.path.join(settings.PROJECT_DIR, "models", "*.pt"))
    model_names = [os.path.basename(p) for p in list_models]

    # Try to find models with sequence length in filename
    matching_models = []
    for model_filename in model_names:
        try:
            seq = model_filename.split("_")[3]
            if int(seq) == sequence_length:
                matching_models.append(model_filename)
        except (IndexError, ValueError):
            continue

    # If we found multiple models for this length, pick the one with highest accuracy in filename
    if len(matching_models) > 1:
        accuracy_models = []
        for filename in matching_models:
            try:
                # expecting filename like model_84_acc_10_frames_final_data.pt
                accuracy = float(filename.split("_")[1])
            except Exception:
                accuracy = 0.0
            accuracy_models.append((accuracy, filename))
        accuracy_models.sort(reverse=True)
        return accuracy_models[0][1]

    if len(matching_models) == 1:
        return matching_models[0]

    # If no exact match, return the first model found as a fallback (if any)
    if model_names:
        return model_names[0]

    return ""

MODEL_CACHE = {}
MODEL_CACHE_LOCK = threading.Lock()

def get_cached_model(sequence_length: int):
    """
    Load (and cache) the correct trained model for the requested `sequence_length`.
    Caching avoids re-downloading/loading ResNeXt and reloading weights each request.
    """
    selected_model_name = get_accurate_model(sequence_length)
    if not selected_model_name:
        return None, ""

    model_path = os.path.join(settings.PROJECT_DIR, 'models', selected_model_name)
    if not os.path.isfile(model_path):
        return None, selected_model_name

    cache_key = (selected_model_name, device.type)
    with MODEL_CACHE_LOCK:
        if cache_key in MODEL_CACHE:
            return MODEL_CACHE[cache_key], selected_model_name

        model = Model(2).to(device)
        state_dict = torch.load(model_path, map_location=device)
        model.load_state_dict(state_dict)
        model.eval()
        MODEL_CACHE[cache_key] = model
        return model, selected_model_name

def _save_uploaded_video_to_project(video_file):
    """
    Save uploaded video into `uploaded_videos` and return absolute path and basename.
    """
    video_file_ext = video_file.name.split('.')[-1].lower()
    saved_video_file = f"uploaded_file_{int(time.time())}.{video_file_ext}"
    if settings.DEBUG:
        target_dir = os.path.join(settings.PROJECT_DIR, 'uploaded_videos')
    else:
        target_dir = os.path.join(settings.PROJECT_DIR, 'uploaded_videos', 'app', 'uploaded_videos')
    os.makedirs(target_dir, exist_ok=True)
    saved_path = os.path.join(target_dir, saved_video_file)
    with open(saved_path, 'wb') as vFile:
        shutil.copyfileobj(video_file, vFile)
    return saved_path, saved_video_file
ALLOWED_VIDEO_EXTENSIONS = set(['mp4','gif','webm','avi','3gp','wmv','flv','mkv'])

def allowed_video_file(filename):
    #print("filename" ,filename.rsplit('.',1)[1].lower())
    if (filename.rsplit('.',1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS):
        return True
    else: 
        return False
def index(request):
    if request.method == 'GET':
        video_upload_form = VideoUploadForm()
        if 'file_name' in request.session:
            del request.session['file_name']
        if 'preprocessed_images' in request.session:
            del request.session['preprocessed_images']
        if 'faces_cropped_images' in request.session:
            del request.session['faces_cropped_images']
        return render(request, index_template_name, {"form": video_upload_form})
    else:
        video_upload_form = VideoUploadForm(request.POST, request.FILES)
        if video_upload_form.is_valid():
            video_file = video_upload_form.cleaned_data['upload_video_file']
            video_file_ext = video_file.name.split('.')[-1]
            sequence_length = video_upload_form.cleaned_data['sequence_length']
            video_content_type = video_file.content_type.split('/')[0]
            if video_content_type in settings.CONTENT_TYPES:
                if video_file.size > int(settings.MAX_UPLOAD_SIZE):
                    video_upload_form.add_error("upload_video_file", "Maximum file size 100 MB")
                    return render(request, index_template_name, {"form": video_upload_form})

            if sequence_length <= 0:
                video_upload_form.add_error("sequence_length", "Sequence Length must be greater than 0")
                return render(request, index_template_name, {"form": video_upload_form})
            
            if allowed_video_file(video_file.name) == False:
                video_upload_form.add_error("upload_video_file","Only video files are allowed ")
                return render(request, index_template_name, {"form": video_upload_form})
            
            saved_video_file = 'uploaded_file_'+str(int(time.time()))+"."+video_file_ext
            if settings.DEBUG:
                with open(os.path.join(settings.PROJECT_DIR, 'uploaded_videos', saved_video_file), 'wb') as vFile:
                    shutil.copyfileobj(video_file, vFile)
                request.session['file_name'] = os.path.join(settings.PROJECT_DIR, 'uploaded_videos', saved_video_file)
            else:
                with open(os.path.join(settings.PROJECT_DIR, 'uploaded_videos','app','uploaded_videos', saved_video_file), 'wb') as vFile:
                    shutil.copyfileobj(video_file, vFile)
                request.session['file_name'] = os.path.join(settings.PROJECT_DIR, 'uploaded_videos','app','uploaded_videos', saved_video_file)
            request.session['sequence_length'] = sequence_length
            return redirect('ml_app:predict')
        else:
            return render(request, index_template_name, {"form": video_upload_form})

def predict_page(request):
    if request.method == "GET":
        # Redirect to 'home' if 'file_name' is not in session
        if 'file_name' not in request.session:
            return redirect("ml_app:home")
        if 'file_name' in request.session:
            video_file = request.session['file_name']
        if 'sequence_length' in request.session:
            sequence_length = request.session['sequence_length']
        path_to_videos = [video_file]
        video_file_name = os.path.basename(video_file)
        video_file_name_only = os.path.splitext(video_file_name)[0]
        # Production environment adjustments
        if not settings.DEBUG:
            production_video_name = os.path.join('/home/app/staticfiles/', video_file_name.split('/')[3])
            print("Production file name", production_video_name)
        else:
            production_video_name = video_file_name

        if face_recognition is None:
            return render(request, predict_template_name, {
                'error': 'Missing dependency: face_recognition. Install project dependencies to enable face detection/cropping.',
            })

        # Load validation dataset
        video_dataset = validation_dataset(path_to_videos, sequence_length=sequence_length, transform=train_transforms)

        # Ensure models folder contains at least one .pt model
        model_files = glob.glob(os.path.join(settings.PROJECT_DIR, 'models', '*.pt'))
        if len(model_files) == 0:
            return render(request, predict_template_name, {
                'error': 'No model files (.pt) found in models folder. Please download the trained model and place it in the models directory.',
                'available_models': [],
            })

        # Load model (choose best matching model for required sequence length)
        # Instantiate model on the selected device
        model = Model(2).to(device)

        selected_model_name = get_accurate_model(sequence_length)
        model_path = os.path.join(settings.PROJECT_DIR, 'models', selected_model_name)
        if not os.path.isfile(model_path):
            return render(request, predict_template_name, {
                'error': f'Could not find model "{selected_model_name}". Available models: {model_files}',
                'available_models': model_files,
            })

        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        start_time = time.time()
        # Display preprocessing images
        print("<=== | Started Videos Splitting | ===>")
        preprocessed_images = []
        faces_cropped_images = []
        cap = cv2.VideoCapture(video_file)
        # Process each frame for preprocessing and face cropping (only first `sequence_length` frames)
        padding = 40
        faces_found = 0
        processed_frames = 0
        for i in range(sequence_length):
            ret, frame = cap.read()
            if not ret:
                break
            processed_frames += 1

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Save preprocessed image
            image_name = f"{video_file_name_only}_preprocessed_{i+1}.png"
            image_path = os.path.join(settings.PROJECT_DIR, 'uploaded_images', image_name)
            img_rgb = pImage.fromarray(rgb_frame, 'RGB')
            img_rgb.save(image_path)
            preprocessed_images.append(image_name)

            # Face detection and cropping
            face_locations = face_recognition.face_locations(rgb_frame)
            if len(face_locations) == 0:
                continue

            top, right, bottom, left = face_locations[0]
            h, w = frame.shape[:2]
            y1 = max(0, top - padding)
            y2 = min(h, bottom + padding)
            x1 = max(0, left - padding)
            x2 = min(w, right + padding)
            if y2 <= y1 or x2 <= x1:
                continue
            frame_face = frame[y1:y2, x1:x2]

            # Convert cropped face image to RGB and save
            rgb_face = cv2.cvtColor(frame_face, cv2.COLOR_BGR2RGB)
            img_face_rgb = pImage.fromarray(rgb_face, 'RGB')
            image_name = f"{video_file_name_only}_cropped_faces_{i+1}.png"
            image_path = os.path.join(settings.PROJECT_DIR, 'uploaded_images', image_name)
            img_face_rgb.save(image_path)
            faces_found += 1
            faces_cropped_images.append(image_name)
        cap.release()

        print(f"Number of processed frames: {processed_frames}")

        print("<=== | Videos Splitting and Face Cropping Done | ===>")
        print("--- %s seconds ---" % (time.time() - start_time))

        # No face detected
        if faces_found == 0:
            return render(request, predict_template_name, {"no_faces": True})

        # Perform prediction
        try:
            heatmap_images = []
            output = ""
            confidence = 0.0

            for i in range(len(path_to_videos)):
                print("<=== | Started Prediction | ===>")
                prediction = predict(model, video_dataset[i], './', video_file_name_only)
                confidence = round(prediction[1], 1)
                output = "REAL" if prediction[0] == 1 else "FAKE"
                print("Prediction:", prediction[0], "==", output, "Confidence:", confidence)
                print("<=== | Prediction Done | ===>")
                print("--- %s seconds ---" % (time.time() - start_time))

                # Uncomment if you want to create heat map images
                # for j in range(sequence_length):
                #     heatmap_images.append(plot_heat_map(j, model, video_dataset[i], './', video_file_name_only))

            # Render results
            context = {
                'preprocessed_images': preprocessed_images,
                'faces_cropped_images': faces_cropped_images,
                'heatmap_images': heatmap_images,
                'original_video': production_video_name,
                'models_location': os.path.join(settings.PROJECT_DIR, 'models'),
                'output': output,
                'confidence': confidence
            }

            if settings.DEBUG:
                return render(request, predict_template_name, context)
            else:
                return render(request, predict_template_name, context)

        except Exception as e:
            print(f"Exception occurred during prediction: {e}")
            return render(request, 'cuda_full.html')

@require_POST
def api_predict(request):
    """
    JSON endpoint for AJAX uploads.
    Returns output/confidence plus the saved video basename (for MEDIA_URL).
    """
    video_upload_form = VideoUploadForm(request.POST, request.FILES)
    if not video_upload_form.is_valid():
        return JsonResponse({"error": "Invalid form submission", "details": video_upload_form.errors}, status=400)

    video_file = video_upload_form.cleaned_data['upload_video_file']
    sequence_length = int(video_upload_form.cleaned_data['sequence_length'])

    if sequence_length <= 0:
        return JsonResponse({"error": "Sequence Length must be greater than 0"}, status=400)

    if allowed_video_file(video_file.name) is False:
        return JsonResponse({"error": "Only video files are allowed"}, status=400)

    if video_file.size > int(settings.MAX_UPLOAD_SIZE):
        return JsonResponse({"error": "Maximum file size 100 MB"}, status=400)

    saved_path, saved_basename = _save_uploaded_video_to_project(video_file)

    try:
        if face_recognition is None:
            return JsonResponse(
                {"error": "Missing dependency: face_recognition. Install project dependencies to enable face detection/cropping."},
                status=500,
            )

        # Inference-only: avoids generating preview images on the server.
        video_dataset = validation_dataset([saved_path], sequence_length=sequence_length, transform=train_transforms)
        model, selected_model_name = get_cached_model(sequence_length)
        if model is None:
            return JsonResponse(
                {"error": f"Model not found for sequence length {sequence_length}", "model": selected_model_name},
                status=500,
            )

        prediction = predict(model, video_dataset[0], './', os.path.splitext(saved_basename)[0])
        confidence = round(prediction[1], 1)
        output = "REAL" if prediction[0] == 1 else "FAKE"

        return JsonResponse({
            "output": output,
            "confidence": confidence,
            "original_video": saved_basename,
            "model_used": selected_model_name,
        })
    except Exception as e:
        return JsonResponse({"error": f"Prediction failed: {str(e)}"}, status=500)
def about(request):
    return render(request, about_template_name)

def handler404(request,exception):
    return render(request, '404.html', status=404)
def cuda_full(request):
    return render(request, 'cuda_full.html')
