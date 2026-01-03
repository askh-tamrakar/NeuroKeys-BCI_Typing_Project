const moves = ['rock', 'paper', 'scissors'];

function getOpponentMove() {
  return moves[Math.floor(Math.random() * moves.length)];
}

function determineWinner(user, opponent) {
  if (user === opponent) return "It's a tie!";
  if (
    (user === 'rock' && opponent === 'scissors') ||
    (user === 'paper' && opponent === 'rock') ||
    (user === 'scissors' && opponent === 'paper')
  ) {
    return "You win!";
  }
  return "You lose!";
}

function updateHandImages(userMove, opponentMove) {
  document.getElementById('user-hand').src = `images/${userMove}.png`;
  document.getElementById('opponent-hand').src = `images/${opponentMove}.png`;
}

function play(userMove) {
  const opponentMove = getOpponentMove();
  const result = determineWinner(userMove, opponentMove);
  updateHandImages(userMove, opponentMove);
  document.getElementById('outcome').textContent = result;
}
function updateHandImages(userMove, opponentMove) {
  document.getElementById('user-hand').src = `images/${userMove}.png`;
  document.getElementById('opponent-hand').src = `images/${opponentMove}.png`;
}
function play(userMove) {
  const opponentMove = getOpponentMove();
  const result = determineWinner(userMove, opponentMove);
  updateHandImages(userMove, opponentMove);
  document.getElementById('outcome').textContent = result;
}
const handImages = {
  rock: 'images/rock.png',
  paper: 'images/paper.png',
  scissors: 'images/scissors.png',
  blank: 'images/blank.png'
};

function play(userChoice) {
  const userImg = document.getElementById('user-hand');
  const oppImg = document.getElementById('opponent-hand');
  const outcomeEl = document.getElementById('outcome');

  // show user's chosen hand
  userImg.src = handImages[userChoice] || handImages.blank;
  // reset opponent while "thinking"
  oppImg.src = handImages.blank;
  outcomeEl.textContent = '...';

  const choices = ['rock', 'paper', 'scissors'];
  const oppChoice = choices[Math.floor(Math.random() * choices.length)];

  // small reveal delay for UX
  setTimeout(() => {
    oppImg.src = handImages[oppChoice];

    if (userChoice === oppChoice) {
      outcomeEl.textContent = "It's a tie.";
    } else if (
      (userChoice === 'rock' && oppChoice === 'scissors') ||
      (userChoice === 'paper' && oppChoice === 'rock') ||
      (userChoice === 'scissors' && oppChoice === 'paper')
    ) {
      outcomeEl.textContent = 'You win!';
    } else {
      outcomeEl.textContent = 'You lose.';
    }
  }, 300);

  }