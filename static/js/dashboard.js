// Initialize Feather icons
document.addEventListener('DOMContentLoaded', () => {
    feather.replace();
    loadDashboardData();

    // Set up refresh button handlers
    document.getElementById('refresh-top-users').addEventListener('click', () => {
        loadTopUsers();
    });

    document.getElementById('refresh-transactions').addEventListener('click', () => {
        loadRecentTransactions();
    });

    document.getElementById('refresh-games').addEventListener('click', () => {
        loadRecentGames();
    });

    // Auto-refresh data every minute
    setInterval(loadDashboardData, 60000);
});

// Main function to load all dashboard data
function loadDashboardData() {
    fetch('/api/stats')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            updateDashboardData(data);
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        })
        .catch(error => {
            console.error('Error fetching dashboard data:', error);
            document.getElementById('status-badge').textContent = 'Error';
            document.getElementById('status-badge').className = 'badge bg-danger';
        });
}

// Update all dashboard elements with new data
function updateDashboardData(data) {
    // Update status badge
    document.getElementById('status-badge').textContent = 'Online';
    document.getElementById('status-badge').className = 'badge bg-success';

    // Update statistics
    document.getElementById('user-count').textContent = data.user_count;
    document.getElementById('total-currency').textContent = formatCurrency(data.total_currency);

    // Update top users
    updateTopUsers(data.top_users);

    // Update recent transactions
    updateRecentTransactions(data.recent_transactions);

    // Update recent games
    updateRecentGames(data.recent_games);
}

// Format currency amounts
function formatCurrency(amount) {
    return '$' + parseFloat(amount).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

// Update top users table
function updateTopUsers(users) {
    const tableBody = document.getElementById('top-users-table');
    if (!users || users.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3" class="text-center">No users found</td></tr>';
        return;
    }

    let html = '';
    users.forEach((user, index) => {
        const rankEmoji = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '';
        html += `
            <tr>
                <td>${index + 1} ${rankEmoji}</td>
                <td>${escapeHtml(user.username)}</td>
                <td>${formatCurrency(user.balance)}</td>
            </tr>
        `;
    });
    tableBody.innerHTML = html;
}

// Update recent transactions table
function updateRecentTransactions(transactions) {
    const tableBody = document.getElementById('transactions-table');
    if (!transactions || transactions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center">No transactions found</td></tr>';
        return;
    }

    let html = '';
    transactions.forEach(tx => {
        const amountClass = tx.amount >= 0 ? 'win-amount' : 'loss-amount';
        const formattedTime = formatDateTime(tx.timestamp);
        
        html += `
            <tr>
                <td>${escapeHtml(tx.username)}</td>
                <td><span class="badge badge-${tx.type.toLowerCase()}">${escapeHtml(tx.type)}</span></td>
                <td class="${amountClass}">${formatCurrency(tx.amount)}</td>
                <td>${formattedTime}</td>
            </tr>
        `;
    });
    tableBody.innerHTML = html;
}

// Update recent games table
function updateRecentGames(games) {
    const tableBody = document.getElementById('games-table');
    if (!games || games.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No games found</td></tr>';
        return;
    }

    let html = '';
    games.forEach(game => {
        const resultClass = game.payout > 0 ? 'win-amount' : 'loss-amount';
        const resultText = game.payout > 0 ? 'Win' : 'Loss';
        const formattedTime = formatDateTime(game.timestamp);
        
        html += `
            <tr>
                <td>${escapeHtml(game.username)}</td>
                <td><span class="badge badge-${game.game_type.toLowerCase()}">${game.game_type === 'slots_extended' ? 'Big Slots' : escapeHtml(game.game_type)}</span></td>
                <td>${formatCurrency(game.bet_amount)}</td>
                <td>${formatCurrency(game.payout)}</td>
                <td class="${resultClass}">${resultText}</td>
                <td>${formattedTime}</td>
            </tr>
        `;
    });
    tableBody.innerHTML = html;
}

// Format date/time for display
function formatDateTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// Function to safely escape HTML content
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Individual data loading functions for refresh buttons
function loadTopUsers() {
    const tableBody = document.getElementById('top-users-table');
    tableBody.innerHTML = '<tr><td colspan="3" class="text-center"><div class="loading-spinner"></div></td></tr>';
    
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            updateTopUsers(data.top_users);
        })
        .catch(error => {
            console.error('Error fetching top users:', error);
            tableBody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Error loading data</td></tr>';
        });
}

function loadRecentTransactions() {
    const tableBody = document.getElementById('transactions-table');
    tableBody.innerHTML = '<tr><td colspan="4" class="text-center"><div class="loading-spinner"></div></td></tr>';
    
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            updateRecentTransactions(data.recent_transactions);
        })
        .catch(error => {
            console.error('Error fetching transactions:', error);
            tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Error loading data</td></tr>';
        });
}

function loadRecentGames() {
    const tableBody = document.getElementById('games-table');
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center"><div class="loading-spinner"></div></td></tr>';
    
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            updateRecentGames(data.recent_games);
        })
        .catch(error => {
            console.error('Error fetching games:', error);
            tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error loading data</td></tr>';
        });
}
