document.addEventListener('DOMContentLoaded', function () {
    const deleteButtons = document.querySelectorAll('.delete-image');

    deleteButtons.forEach(button => {
        button.addEventListener('click', function () {
            const imageId = this.dataset.id;
            const filepath = this.dataset.filepath;

            if (confirm(`Are you sure you want to delete image ${imageId}?`)) {
                fetch(`/delete`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ filepath: filepath })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.message) {
                        alert(data.message);
                        // Remove the image row from the table
                        this.closest('tr').remove();
                    } else {
                        alert(data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error deleting image.');
                });
            }
        });
    });
});
