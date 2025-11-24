let currentFile = null;
let uploadSessionId = null;

// Configuración del área de drag & drop
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const selectVideoBtn = document.getElementById('selectVideoBtn');

// Eventos de drag & drop
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-primary', 'bg-light');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-primary', 'bg-light');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-primary', 'bg-light');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

dropZone.addEventListener('click', () => {
    fileInput.click();
});

// Agregar event listener para el botón con stopPropagation
selectVideoBtn.addEventListener('click', (e) => {
    e.stopPropagation(); // Esto evita que el evento se propague al dropZone
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

function handleFile(file) {
    // Validar tipo de archivo
    if (!file.type.startsWith('video/')) {
        alert('Por favor selecciona un archivo de video válido.');
        return;
    }
    
    // Validar tamaño (500 MB)
    if (file.size > 500 * 1024 * 1024) {
        alert('El archivo es demasiado grande. Tamaño máximo: 500 MB');
        return;
    }
    
    currentFile = file;
    
    // Mostrar información del archivo
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
    document.getElementById('fileType').textContent = file.type;
    document.getElementById('blobName').value = file.name;
    
    // Mostrar sección de información
    document.getElementById('fileInfo').style.display = 'block';
    
    // Ocultar área de drop
    dropZone.style.display = 'none';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

document.getElementById('startUpload').addEventListener('click', async () => {
    if (!currentFile) return;
    
    const blobName = document.getElementById('blobName');
    if (!blobName || !blobName.value) {
        alert('Por favor especifica un nombre para el archivo en S3.');
        return;
    }

    const title = document.getElementById('title').value;
    const description = document.getElementById('description').value;
    
    // Mostrar progreso
    const progressContainer = document.getElementById('progressContainer');
    const startUpload = document.getElementById('startUpload');
    const uploadStatus = document.getElementById('uploadStatus');
    
    if (progressContainer) progressContainer.style.display = 'block';
    if (startUpload) startUpload.disabled = true;
    
    try {
        // Crear FormData con el archivo real
        const formData = new FormData();
        formData.append('video', currentFile);
        formData.append('title', document.getElementById('title').value);
        formData.append('description', document.getElementById('description').value);
        
        // Obtener token CSRF
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfToken) {
            throw new Error('Token CSRF no encontrado');
        }
        formData.append('csrfmiddlewaretoken', csrfToken.value);
        
        // Obtener URL del atributo data-upload-url o usar la URL actual
        const uploadUrl = document.getElementById('startUpload').dataset.uploadUrl || window.location.href;
        
        const response = await fetch(uploadUrl, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            if (uploadStatus) {
                uploadStatus.textContent = '¡Subida completada exitosamente!';
                uploadStatus.classList.add('text-success');
                uploadStatus.classList.remove('text-danger');
            }
            // Recargar página después de 2 segundos
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            throw new Error(result.error || 'Error en la subida');
        }
        
    } catch (error) {
        console.error('Error:', error);
        if (uploadStatus) {
            uploadStatus.textContent = 'Error: ' + error.message;
            uploadStatus.classList.add('text-danger');
            uploadStatus.classList.remove('text-success');
        }
        if (startUpload) startUpload.disabled = false;
    }
});

function showSuccess(message) {
    const uploadStatus = document.getElementById('uploadStatus');
    if (uploadStatus) {
        uploadStatus.textContent = message;
        uploadStatus.classList.add('text-success');
        uploadStatus.classList.remove('text-danger', 'text-warning');
    }
}

function showWarning(message) {
    const uploadStatus = document.getElementById('uploadStatus');
    if (uploadStatus) {
        uploadStatus.textContent = message;
        uploadStatus.classList.add('text-warning');
        uploadStatus.classList.remove('text-success', 'text-danger');
    }
    // También mostrar en consola para debugging
    console.warn('Advertencia:', message);
}

function showVideoPreview(videoUrl, filename) {
    // Construir URL completa de S3 con la configuración correcta
    const s3BaseUrl = 'https://tcefbucket.s3.us-east-2.amazonaws.com/';
    const fullVideoUrl = s3BaseUrl + videoUrl;
    
    console.log('Video URL:', videoUrl);
    console.log('Full Video URL:', fullVideoUrl);
    
    // Configurar el modal
    document.getElementById('videoTitle').textContent = filename;
    document.getElementById('videoSource').src = fullVideoUrl;
    document.getElementById('downloadLink').href = fullVideoUrl;
    
    // Cargar el video
    const videoPlayer = document.getElementById('videoPlayer');
    videoPlayer.load();
    
    // Mostrar el modal
    const modal = new bootstrap.Modal(document.getElementById('videoPreviewModal'));
    modal.show();
    
    // Agregar event listener para detener el video cuando se cierre el modal
    const videoModal = document.getElementById('videoPreviewModal');
    videoModal.addEventListener('hidden.bs.modal', function () {
        // Detener y resetear el video
        videoPlayer.pause();
        videoPlayer.currentTime = 0;
        videoPlayer.src = '';
        console.log('Video detenido y reseteado');
    });
}

function confirmDeleteVideo(videoId, filename, s3Key) {
    // Configurar el modal de confirmación
    document.getElementById('deleteVideoName').textContent = filename;
    
    // Configurar el botón de confirmación
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    confirmBtn.onclick = () => deleteVideo(videoId, s3Key);
    
    // Mostrar el modal
    const modal = new bootstrap.Modal(document.getElementById('deleteVideoModal'));
    modal.show();
}

async function deleteVideo(videoId, s3Key) {
    try {
        // Mostrar estado de carga
        const confirmBtn = document.getElementById('confirmDeleteBtn');
        const originalText = confirmBtn.innerHTML;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Eliminando...';
        confirmBtn.disabled = true;
        
        // Obtener token CSRF
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfToken) {
            throw new Error('Token CSRF no encontrado');
        }
        
        // Enviar solicitud de eliminación
        const response = await fetch(`/admin-panel/videos/delete/${videoId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken.value,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                s3_key: s3Key
            })
        });
        
        // Verificar si la respuesta es JSON
        let result;
        try {
            result = await response.json();
        } catch (e) {
            throw new Error('Error al procesar la respuesta del servidor');
        }
        
        if (result.success) {
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('deleteVideoModal'));
            if (modal) {
                modal.hide();
            }
            
            // Mostrar mensaje de éxito o advertencia
            if (result.warning) {
                // Si hay una advertencia (problema con S3 pero eliminado de BD)
                showWarning(result.message || 'Video eliminado con advertencias');
            } else {
                showSuccess(result.message || 'Video eliminado exitosamente');
            }
            
            // Recargar página después de 1.5 segundos
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            throw new Error(result.error || 'Error al eliminar el video');
        }
        
    } catch (error) {
        console.error('Error:', error);
        
        // Restaurar botón
        const confirmBtn = document.getElementById('confirmDeleteBtn');
        if (confirmBtn) {
            confirmBtn.innerHTML = originalText;
            confirmBtn.disabled = false;
        }
        
        // Mostrar error
        showError('Error al eliminar el video: ' + error.message);
    }
}

function showError(errorMessage) {
    document.getElementById('errorMessage').textContent = errorMessage;
    const modal = new bootstrap.Modal(document.getElementById('errorModal'));
    modal.show();
}

