const btnEliminar = document.querySelectorAll('.btn-delete')

if (btnEliminar) {
    const btnArray = Array.from(btnEliminar);
    btnArray.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            if (!confirm('¿Estás seguro de que quieres eliminarlo?')) {
                e.preventDefault();
            }
        });
    });
}