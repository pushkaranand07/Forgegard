function getCookie(name) {
  const cookieString = document.cookie || '';
  const cookies = cookieString.split(';').map(c => c.trim());
  for (const c of cookies) {
    if (c.startsWith(name + '=')) {
      return decodeURIComponent(c.substring(name.length + 1));
    }
  }
  return null;
}

$(function () {
  const $form = $('#uploadForm');
  const $fileInput = $('#id_upload_video_file');
  const $dropzone = $('#dropzone');
  const $browseBtn = $('#browseBtn');
  const $video = $('#videos');
  const $videoSource = $('#video_source');
  const $fileMeta = $('#fileMeta');
  const $uploadError = $('#uploadError');
  const $loading = $('#loading');
  const $result = $('#result');
  const $tryAgain = $('#tryAgain');
  const $submitBtn = $('#videoUpload');

  const allowedExt = ['mp4', 'gif', 'webm', 'avi', '3gp', 'wmv', 'flv', 'mkv'];
  const maxSizeBytes = 104857600; // 100 MB

  function setError(msg) {
    $uploadError.text(msg).removeClass('d-none');
  }

  function clearError() {
    $uploadError.addClass('d-none').text('');
  }

  function showPreview(file) {
    if (!file) return;
    const objectUrl = URL.createObjectURL(file);
    $videoSource.attr('src', objectUrl);
    $video.removeClass('d-none');
    $video[0].load();
  }

  function validateFile(file) {
    if (!file) return 'Please select a video file.';
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!allowedExt.includes(ext)) return 'Invalid file type. Please upload a video.';
    if (file.size > maxSizeBytes) return 'File too large. Maximum size is 100 MB.';
    return null;
  }

  $browseBtn.on('click', function () {
    $fileInput.trigger('click');
  });

  $dropzone.on('click', function () {
    $fileInput.trigger('click');
  });

  $dropzone.on('dragover', function (e) {
    e.preventDefault();
    e.stopPropagation();
    $dropzone.addClass('border-primary');
  });

  $dropzone.on('dragleave', function (e) {
    e.preventDefault();
    e.stopPropagation();
    $dropzone.removeClass('border-primary');
  });

  $dropzone.on('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    $dropzone.removeClass('border-primary');

    const files = e.originalEvent && e.originalEvent.dataTransfer ? e.originalEvent.dataTransfer.files : e.dataTransfer.files;
    const file = files && files.length ? files[0] : null;
    const err = validateFile(file);
    if (err) {
      clearError();
      setError(err);
      return;
    }
    clearError();
    showPreview(file);
    $fileMeta.text(`${file.name} (${Math.round(file.size / 1024 / 1024)} MB)`);

    // Assign dropped file to the input (workaround for some browsers)
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    $fileInput[0].files = dataTransfer.files;
  });

  $fileInput.on('change', function () {
    clearError();
    const file = this.files && this.files.length ? this.files[0] : null;
    const err = validateFile(file);
    if (err) {
      setError(err);
      return;
    }
    $fileMeta.text(file ? `${file.name} (${Math.round(file.size / 1024 / 1024)} MB)` : '');
    showPreview(file);
  });

  $tryAgain.on('click', function () {
    $result.addClass('d-none').empty();
    $uploadError.addClass('d-none').text('');
    $loading.addClass('d-none');
    $tryAgain.addClass('d-none');
    $fileMeta.text('');
    $fileInput.val('');
    $videoSource.attr('src', '');
    $video[0].pause();
    $video.addClass('d-none');
    $submitBtn.prop('disabled', false).text('Detect');
  });

  $form.on('submit', function (e) {
    e.preventDefault();
    clearError();

    const file = $fileInput[0].files && $fileInput[0].files.length ? $fileInput[0].files[0] : null;
    const err = validateFile(file);
    if (err) {
      setError(err);
      return;
    }

    const formData = new FormData(this);

    $submitBtn.prop('disabled', true);
    $submitBtn.html('Processing... <span class="spinner-border spinner-border-sm ms-2" role="status" aria-hidden="true"></span>');
    $loading.removeClass('d-none');
    $result.addClass('d-none').empty();

    $.ajax({
      type: 'POST',
      url: '/api/predict/',
      data: formData,
      contentType: false,
      processData: false,
      headers: {
        'X-CSRFToken': getCookie('csrftoken')
      },
      success: function (data) {
        $loading.addClass('d-none');
        $submitBtn.prop('disabled', false).text('Detect');
        $tryAgain.removeClass('d-none');

        const confidence = Number(data.confidence || 0);
        const pctWidth = Math.max(0, Math.min(100, confidence));
        const badgeClass = data.output === 'REAL' ? 'text-success' : 'text-danger';
        const outputText = data.output || '—';

        const videoUrl = (data.original_video ? ('/media/' + data.original_video) : '');
        if (videoUrl) {
          $videoSource.attr('src', videoUrl);
          $video.removeClass('d-none');
          $video[0].load();
        }

        $result.removeClass('d-none').html(`
          <div class="card border-0 shadow-sm">
            <div class="card-body">
              <div class="d-flex align-items-center justify-content-between">
                <div class="fs-5 fw-semibold ${badgeClass}">Prediction: ${outputText}</div>
                <div class="text-muted small">Model: ${data.model_used || ''}</div>
              </div>
              <div class="mt-3">
                <div class="d-flex justify-content-between">
                  <span class="text-muted">Confidence</span>
                  <span class="fw-semibold">${confidence}%</span>
                </div>
                <div class="progress mt-2" style="height: 14px;">
                  <div class="progress-bar ${data.output === 'REAL' ? 'bg-success' : 'bg-danger'} progress-bar-striped progress-bar-animated" style="width: ${pctWidth}%"></div>
                </div>
              </div>
            </div>
          </div>
        `);
      },
      error: function (xhr) {
        $loading.addClass('d-none');
        $submitBtn.prop('disabled', false).text('Detect');
        $tryAgain.addClass('d-none');

        let msg = 'Prediction failed.';
        if (xhr.responseJSON && xhr.responseJSON.error) msg = xhr.responseJSON.error;
        setError(msg);
      }
    });
  });
});

