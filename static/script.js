function openLesson(title, content) {
    const viewPanel = document.getElementById('lesson-view');
    if (!viewPanel) return;
    document.getElementById('lesson-title').innerText = title;
    document.getElementById('lesson-text').innerText = content;
    viewPanel.style.display = 'block';
}

function checkQuizAnswer(buttonElement, isCorrect, feedbackId) {
    const parentBox = buttonElement.closest('.box');
    const options = parentBox.querySelectorAll('.opt-btn');

    options.forEach(opt => {
        opt.style.backgroundColor = '#f2f3f5';
        opt.style.color = '#1d2023';
    });

    if (isCorrect) {
        buttonElement.style.backgroundColor = '#1aa64b';
        buttonElement.style.color = '#ffffff';
    } else {
        buttonElement.style.backgroundColor = '#e30613';
        buttonElement.style.color = '#ffffff';
    }

    document.getElementById(feedbackId).style.display = 'block';
}

function handlePhishing(clickedReport) {
    const feedback = document.getElementById('inbox-feedback');
    if (!feedback) return;
    feedback.style.display = 'block';

    if (clickedReport) {
        feedback.style.backgroundColor = '#d4edda';
        feedback.style.borderColor = '#1aa64b';
        feedback.style.color = '#1aa64b';
        feedback.innerHTML = '<strong>Отлично!</strong> Вы распознали фишинг. Ссылка вела на сторонний вредоносный домен.';
    } else {
        feedback.style.backgroundColor = '#fce8e6';
        feedback.style.borderColor = '#e30613';
        feedback.style.color = '#e30613';
        feedback.innerHTML = '<strong>Ошибка.</strong> Это фишинговое письмо! Переход по ссылке украл бы данные.';
    }
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const container = document.getElementById('chat-area');
    if (!input || !input.value.trim()) return;

    const userDiv = document.createElement('div');
    userDiv.className = 'msg out';
    userDiv.innerText = input.value;
    container.appendChild(userDiv);

    const text = input.value.toLowerCase();
    input.value = '';
    container.scrollTop = container.scrollHeight;

    setTimeout(() => {
        const botDiv = document.createElement('div');
        botDiv.className = 'msg in';

        if (text.includes('парол')) {
            botDiv.innerText = 'Пароли нужно хранить в менеджере паролей и не использовать одно слово для всех сайтов.';
        } else if (text.includes('фишинг')) {
            botDiv.innerText = 'Если сомневаетесь в письме — посмотрите на домен отправителя. Банки не просят вводить пароли на левых сайтах.';
        } else if (text.includes('социальн') || text.includes('инженер')) {
            botDiv.innerText = 'Социальная инженерия строится на уловках и спешке. Никогда не поддавайтесь панике и перепроверяйте информацию.';
        } else {
            botDiv.innerText = 'Рекомендую почитать уроки в разделе Курсов, там много полезного про актуальные угрозы!';
        }

        container.appendChild(botDiv);
        container.scrollTop = container.scrollHeight;
    }, 1000);
}

function addEmployee() {
    const name = prompt("Введите имя и роль нового сотрудника:");
    if (!name || name.trim() === "") return;

    const tbody = document.getElementById('employees-list');
    if (!tbody) return;

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><span class="tag-name" onclick="editEmployeeName(this)">${name}</span></td>
        <td>0 / 100</td>
        <td class="warn-status">В зоне риска</td>
        <td><button class="btn-del" onclick="deleteEmployee(this)">Удалить</button></td>
    `;
    tbody.appendChild(tr);
}

function editEmployeeName(element) {
    const current = element.innerText;
    const updated = prompt("Редактирование имени сотрудника:", current);
    if (updated && updated.trim() !== "") {
        element.innerText = updated;
    }
}

function deleteEmployee(buttonElement) {
    if (confirm("Вы уверены, что хотите удалить этого сотрудника?")) {
        const row = buttonElement.closest('tr');
        if (row) row.remove();
    }
}

function changeAvatar(seed) {
    const img = document.getElementById('profile-pic');
    if (img) {
        img.src = `https://api.dicebear.com/7.x/bottts/svg?seed=${seed}`;
    }
}

function saveProfileData() {
    const name = document.getElementById('input-profile-name').value;
    const role = document.getElementById('input-profile-role').value;

    const displayNm = document.getElementById('profile-display-name');
    const displayRl = document.getElementById('profile-display-role');
    const status = document.getElementById('profile-save-status');

    if (displayNm && name.trim() !== "") displayNm.innerText = name;
    if (displayRl && role.trim() !== "") displayRl.innerText = role;

    if (status) {
        status.style.display = 'block';
        setTimeout(() => { status.style.display = 'none'; }, 3000);
    }
}
