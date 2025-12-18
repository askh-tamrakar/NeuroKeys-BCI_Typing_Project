/*
  Rock Paper Scissors Game for Arduino
  
  Instructions:
  1. Upload this sketch to your Arduino.
  2. Open the Serial Monitor (Tools > Serial Monitor).
  3. Set Baud Rate to 9600.
  4. Type 'R', 'P', or 'S' (or 'r', 'p', 's') and hit Enter to play.
*/

const char ROCK = 'r';
const char PAPER = 'p';
const char SCISSORS = 's';

void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0)); // Seed random number generator with unconnected pin noise
  
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
  
  Serial.println("Welcome to Rock, Paper, Scissors!");
  Serial.println("Enter 'R' for Rock, 'P' for Paper, or 'S' for Scissors.");
  Serial.println("-------------------------------------------------------");
}

void loop() {
  if (Serial.available() > 0) {
    char userChoice = tolower(Serial.read());
    
    // Ignore newline characters or carriage returns often sent by Serial Monitor
    if (userChoice == '\n' || userChoice == '\r' || userChoice == ' ') {
      return;
    }

    if (isValidChoice(userChoice)) {
      char computerChoice = getComputerChoice();
      
      Serial.print("You chose: ");
      printChoice(userChoice);
      Serial.print("\tComputer chose: ");
      printChoice(computerChoice);
      
      determineWinner(userChoice, computerChoice);
      Serial.println("-------------------------------------------------------");
      Serial.println("Play again? (Enter R, P, or S)");
    } else {
      Serial.println("Invalid input! Please enter R, P, or S.");
    }
  }
}

boolean isValidChoice(char choice) {
  return (choice == ROCK || choice == PAPER || choice == SCISSORS);
}

char getComputerChoice() {
  int randNum = random(0, 3);
  switch (randNum) {
    case 0: return ROCK;
    case 1: return PAPER;
    case 2: return SCISSORS;
  }
  return ROCK; // Should not reach here
}

void printChoice(char choice) {
  if (choice == ROCK) Serial.print("Rock");
  else if (choice == PAPER) Serial.print("Paper");
  else if (choice == SCISSORS) Serial.print("Scissors");
}

void determineWinner(char user, char computer) {
  if (user == computer) {
    Serial.println("\nIt's a Tie!");
  } 
  else if ((user == ROCK && computer == SCISSORS) ||
           (user == PAPER && computer == ROCK) ||
           (user == SCISSORS && computer == PAPER)) {
    Serial.println("\nYou Win!");
  } 
  else {
    Serial.println("\nComputer Wins!");
  }
}
