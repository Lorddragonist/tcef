// Variables globales para el filtrado
let allUsers = [];
let filteredUsers = [];
let currentSort = 'progress';

// Inicializar datos al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    // Recopilar todos los usuarios de la tabla
    const userRows = document.querySelectorAll('.user-row');
    allUsers = Array.from(userRows).map(row => {
        const userId = row.getAttribute('onclick').match(/\d+/)[0];
        const userName = row.querySelector('.fw-bold').textContent.trim();
        const userEmail = row.querySelector('.text-muted').textContent.trim();
        const exerciseCount = parseInt(row.cells[1].querySelector('.metric-value').textContent);
        const progress = parseFloat(row.cells[2].querySelector('small').textContent.replace('%', ''));
        const currentStreak = parseInt(row.cells[3].querySelector('.streak-badge').textContent.replace(' semanas', ''));
        const bestStreak = parseInt(row.cells[4].querySelector('.best-streak-badge').textContent.replace(' semanas', ''));
        
        return {
            element: row,
            userId: userId,
            userName: userName,
            userEmail: userEmail,
            exerciseCount: exerciseCount,
            progress: progress,
            currentStreak: currentStreak,
            bestStreak: bestStreak
        };
    });
    
    filteredUsers = [...allUsers];
    
    // Configurar eventos de búsqueda
    setupSearch();
    setupSorting();
    
    // Definir setupTestData si no existe
    if (typeof window.setupTestData !== 'function') {
        window.setupTestData = function() {
            console.log('setupTestData called from user_monitoring');
            // Implementar funcionalidad de datos de prueba si es necesario
        };
    }
    
    // Definir funciones globales para modales
    if (typeof window.filterChart !== 'function') {
        window.filterChart = function() {
            console.log('filterChart called from user_monitoring');
            // Esta función se implementará en el modal cuando sea necesario
        };
    }
    
    if (typeof window.resetChart !== 'function') {
        window.resetChart = function() {
            console.log('resetChart called from user_monitoring');
            // Esta función se implementará en el modal cuando sea necesario
        };
    }
    
    if (typeof window.changeMetric !== 'function') {
        window.changeMetric = function() {
            console.log('changeMetric called from user_monitoring');
            // Esta función se implementará en el modal cuando sea necesario
        };
    }
    
    // Llamar setupTestData
    setupTestData();
});

function setupSearch() {
    const searchInput = document.getElementById('userSearch');
    const clearButton = document.getElementById('clearSearch');
    const userCount = document.getElementById('userCount');
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        
        if (searchTerm === '') {
            // Restaurar todos los usuarios cuando no hay término de búsqueda
            filteredUsers = [...allUsers];
        } else {
            // Filtrar usuarios según el término de búsqueda
            filteredUsers = allUsers.filter(user => 
                user.userName.toLowerCase().includes(searchTerm) ||
                user.userEmail.toLowerCase().includes(searchTerm) ||
                user.userId.toLowerCase().includes(searchTerm)
            );
        }
        
        updateTable();
        userCount.textContent = filteredUsers.length;
    });
    
    // Evento para cuando se borra el contenido del input
    searchInput.addEventListener('keyup', function() {
        if (this.value === '') {
            filteredUsers = [...allUsers];
            updateTable();
            userCount.textContent = filteredUsers.length;
        }
    });
    
    clearButton.addEventListener('click', function() {
        searchInput.value = '';
        filteredUsers = [...allUsers];
        updateTable();
        userCount.textContent = filteredUsers.length;
    });
}

function setupSorting() {
    const sortByProgress = document.getElementById('sortByProgress');
    const sortByStreak = document.getElementById('sortByStreak');
    const sortByName = document.getElementById('sortByName');
    
    console.log('Setting up sorting buttons...');
    console.log('sortByProgress:', sortByProgress);
    console.log('sortByStreak:', sortByStreak);
    console.log('sortByName:', sortByName);
    
    if (sortByProgress) {
        sortByProgress.addEventListener('click', function() {
            console.log('Progress sort clicked');
            currentSort = 'progress';
            sortUsers('progress');
            updateSortButtons(this);
        });
    }
    
    if (sortByStreak) {
        sortByStreak.addEventListener('click', function() {
            console.log('Streak sort clicked');
            currentSort = 'streak';
            sortUsers('streak');
            updateSortButtons(this);
        });
    }
    
    if (sortByName) {
        sortByName.addEventListener('click', function() {
            console.log('Name sort clicked');
            currentSort = 'name';
            sortUsers('name');
            updateSortButtons(this);
        });
    }
}


function sortUsers(sortType) {
    console.log('Sorting by:', sortType);
    console.log('Filtered users before sort:', filteredUsers.length);
    
    switch(sortType) {
        case 'progress':
            filteredUsers.sort((a, b) => b.progress - a.progress);
            break;
        case 'streak':
            filteredUsers.sort((a, b) => b.currentStreak - a.currentStreak);
            break;
        case 'name':
            filteredUsers.sort((a, b) => a.userName.localeCompare(b.userName));
            break;
    }
    
    console.log('Filtered users after sort:', filteredUsers.length);
    updateTable();
}

function updateSortButtons(activeButton) {
    // Remover clase activa de todos los botones
    document.querySelectorAll('#sortByProgress, #sortByStreak, #sortByName').forEach(btn => {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
    });
    
    // Agregar clase activa al botón seleccionado
    activeButton.classList.remove('btn-outline-primary');
    activeButton.classList.add('btn-primary');
}

function updateTable() {
    const tbody = document.querySelector('.metrics-table tbody');
    const noResultsRow = tbody.querySelector('tr td[colspan="10"]');
    
    // Remover fila de "no hay usuarios" si existe
    if (noResultsRow) {
        noResultsRow.parentElement.remove();
    }
    
    // Ocultar todas las filas primero
    allUsers.forEach(user => {
        user.element.style.display = 'none';
    });
    
    // Mostrar solo los usuarios filtrados
    if (filteredUsers.length === 0) {
        // Crear fila de "no hay resultados" solo si hay un término de búsqueda
        const searchInput = document.getElementById('userSearch');
        if (searchInput && searchInput.value.trim() !== '') {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center py-4">
                        <i class="fas fa-search fa-2x text-muted mb-3"></i>
                        <div class="text-muted">No se encontraron usuarios que coincidan con la búsqueda</div>
                    </td>
                </tr>
            `;
        }
    } else {
        // Mostrar usuarios filtrados en el orden correcto
        filteredUsers.forEach((user, index) => {
            user.element.style.display = '';
            // Asegurar que el orden se mantenga en el DOM
            if (index === 0) {
                tbody.insertBefore(user.element, tbody.firstChild);
            } else {
                const previousUser = filteredUsers[index - 1];
                tbody.insertBefore(user.element, previousUser.element.nextSibling);
            }
        });
    }
}

function openUserModal(userId) {
    const modal = new bootstrap.Modal(document.getElementById('userDetailModal'));
    const content = document.getElementById('userDetailContent');
    
    // Mostrar loading
    content.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
            <div class="mt-2">Cargando detalles del usuario...</div>
        </div>
    `;
    
    modal.show();
    
    // Cargar contenido del usuario
    fetch(`/admin-panel/monitoring/user/${userId}/details/`)
        .then(response => {
            return response.text();
        })
        .then(html => {
            // Limpiar completamente el contenido antes de insertar el nuevo
            content.innerHTML = '';
            
            // Insertar el nuevo HTML
            content.innerHTML = html;
            
            // Forzar la ejecución del nuevo script inmediatamente
            const scripts = content.querySelectorAll('script');
            
            if (scripts.length > 0) {
                scripts.forEach((script, index) => {
                    try {
                        eval(script.textContent);
                    } catch (e) {
                        console.error('Error ejecutando script:', e);
                    }
                });
                
                // Esperar un poco y verificar si la función está disponible
                setTimeout(() => {
                    if (typeof window.initializeUserDetailChart === 'function') {
                        window.initializeUserDetailChart();
                    }
                }, 200);
            }
        })
        .catch(error => {
            console.error('Error en fetch:', error);
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar los detalles del usuario.
                </div>
            `;
        });
}

// Navegación de meses en el modal
function changeMonth(userId, year, month) {
    const content = document.getElementById('userDetailContent');
    
    // Validar y normalizar mes y año
    let normalizedYear = parseInt(year);
    let normalizedMonth = parseInt(month);
    
    // Normalizar si el mes está fuera de rango
    if (normalizedMonth < 1) {
        normalizedMonth = 12;
        normalizedYear -= 1;
    } else if (normalizedMonth > 12) {
        normalizedMonth = 1;
        normalizedYear += 1;
    }
    
    // Asegurar que el mes esté en el rango válido (1-12)
    normalizedMonth = Math.max(1, Math.min(12, normalizedMonth));
    
    // Mostrar loading
    content.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
            <div class="mt-2">Cargando datos del mes...</div>
        </div>
    `;
    
    // Cargar nuevo contenido con valores normalizados
    fetch(`/admin-panel/monitoring/user/${userId}/details/?year=${normalizedYear}&month=${normalizedMonth}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Error al cargar los datos');
            }
            return response.text();
        })
        .then(html => {
            content.innerHTML = html;
            
            // Ejecutar scripts del nuevo contenido
            const scripts = content.querySelectorAll('script');
            scripts.forEach(script => {
                try {
                    eval(script.textContent);
                } catch (e) {
                    console.error('Error ejecutando script:', e);
                }
            });
            
            // Inicializar gráfico si existe
            setTimeout(() => {
                if (typeof window.initializeUserDetailChart === 'function') {
                    window.initializeUserDetailChart();
                }
            }, 200);
        })
        .catch(error => {
            console.error('Error en fetch:', error);
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error al cargar los datos del mes: ${error.message}
                </div>
            `;
        });
}

