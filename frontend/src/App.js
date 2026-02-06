// Filename: frontend/src/App.js
// Final Version with Mock OTP (Google Sheets) Integration

import React, { useState, useRef, useCallback } from 'react';
import Webcam from 'react-webcam';
import './App.css';

// No Firebase imports needed!

const apiUrl = 'http://127.0.0.1:5000';

function App() {
  const [view, setView] = useState('home'); 
  const [loggedInVoter, setLoggedInVoter] = useState(null);
  
  // --- New State for Registration ---
  const [aadhaarNumber, setAadhaarNumber] = useState('');
  const [userName, setUserName] = useState(''); // To store the name we get from the backend
  const [otp, setOtp] = useState('');
  const [showOtpInput, setShowOtpInput] = useState(false);
  
  const [message, setMessage] = useState({ text: '', type: '' });
  const webcamRef = useRef(null);
  const capture = useCallback(() => webcamRef.current.getScreenshot(), [webcamRef]);
  // ✅ ADDED for liveness detection (blink + head movement)
const captureFrames = async () => {
  const frames = [];

  for (let i = 0; i < 12; i++) {
    const image = webcamRef.current?.getScreenshot();
    if (image) frames.push(image);
    await new Promise(resolve => setTimeout(resolve, 350));
  }

  return frames;
};


  const showMessage = (text, type) => setMessage({ text, type });
  const changeView = (newView) => {
    setMessage({ text: '', type: '' });
    // Reset registration state when changing views
    setAadhaarNumber('');
    setUserName('');
    setOtp('');
    setShowOtpInput(false);
    setView(newView);
};


  // --- NEW: Handle Sending the Mock OTP ---
  const handleSendOtp = async () => {
    showMessage("Verifying Aadhaar & generating OTP...", 'info');
    
    try {
      // Call our *own* backend instead of Firebase
      const response = await fetch(`${apiUrl}/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aadhaarNumber }),
      });

      const result = await response.json();

      if (response.status === 200) {
        setUserName(result.name); // Save the user's name
        setShowOtpInput(true); // Show the OTP input field
        showMessage(`OTP generated for ${result.name}. (Check your Flask terminal for the code)`, 'success');
      } else {
        showMessage(`Error: ${result.error}`, 'error');
      }
    } catch (err) {
      showMessage("Failed to connect to the server.", 'error');
    }
  };

  // --- NEW: Handle Verifying OTP & Registering ---
  const handleVerifyAndRegister = async (event) => {
    event.preventDefault(); // This is a form submission
    
    if (otp.length < 6) {
      showMessage("Please enter the 6-digit OTP.", 'error');
      return;
    }

    showMessage("Verifying OTP and registering...", 'info');
    
    try {
      // --- 1. Capture face ---
      const imageData = capture();
      if (!imageData) {
        showMessage('Could not capture image.', 'error');
        return;
      }

      // --- 2. Send ALL data to our Flask backend ---
      const response = await fetch(`${apiUrl}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aadhaarNumber, otp, imageData }),
      });
      
      const result = await response.json();
      
      if (response.status === 201) {
        showMessage(result.message + " You can now login.", 'success');
        changeView('login'); // Switch to login view
      } else {
        showMessage(`Error: ${result.error}`, 'error');
      }
    } catch (err) {
      showMessage("Failed to register. (Server error)", 'error');
    }
  };

  // --- Login & Vote Handlers (Unchanged) ---
  const handleLogin = async () => {
  showMessage(
    'Please blink your eyes and turn your head left and right',
    'info'
  );

  const images = await captureFrames();

  if (!images || images.length < 5) {
    showMessage('Failed to capture enough frames', 'error');
    return;
  }

  try {
    const response = await fetch(`${apiUrl}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ images }),
    });

    const result = await response.json();

    if (response.status === 200) {
      showMessage(result.message, 'success');
      setLoggedInVoter({
        voterName: result.voterName,
        voterId: result.voterId,
      });
      setView('voting');
    } else {
      showMessage(`Error: ${result.error}`, 'error');
    }
  } catch (err) {
    showMessage('Server connection failed', 'error');
  }
};

  
  const handleVote = async (candidate) => { /* ... (this code is unchanged) ... */
    showMessage(`Casting your vote for ${candidate}...`, 'info');
    try {
      const response = await fetch(`${apiUrl}/vote`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
              voterId: loggedInVoter.voterId,
              candidateId: candidate
          }),
      });
      const result = await response.json();
      if(response.status === 200){
          showMessage(result.message, 'success');
          setTimeout(() => {
              setView('login');
              setLoggedInVoter(null);
              showMessage('You have successfully voted.', 'success');
          }, 3000);
      } else {
          showMessage(`Error: ${result.error}`, 'error');
      }
    } catch (err) {
      showMessage('Error: Failed to connect to the server.', 'error');
    }
  };
  
  // --- Render Functions ---
  
  const renderHomeView = () => ( /* ... (this code is unchanged) ... */
    <div className="page-container home-page">
      <h2>Welcome to the Secure E-Voting System</h2>
      <p className="subtitle">Your voice, secured by technology. This system uses a mock Aadhaar registry and facial recognition.</p>
      
      <div className="process-steps">
        <div className="step-card">
          <h3>Step 1: Register</h3>
          <p>Go to the 'Register' page, enter your 12-digit Aadhaar number. An OTP will be generated in the backend terminal.</p>
        </div>
        <div className="step-card">
          <h3>Step 2: Verify</h3>
          <p>Enter the OTP from the terminal and capture your face to complete your secure registration.</p>
        </div>
        <div className="step-card">
          <h3>Step 3: Vote</h3>
          <p>Login using only your face. Once authenticated, cast your vote. You can only vote once.</p>
        </div>
      </div>
      <div className="home-cta">
        <h3>Meet the Candidates</h3>
        <p>Learn about the candidates running in this election before you cast your vote.</p>
        <button className="button-primary" onClick={() => changeView('candidates')}>View Candidates</button>
      </div>
    </div>
  );

  // --- MODIFIED: Registration View ---
  const renderRegisterView = () => (
    <div className="page-container">
      <h2>Voter Registration</h2>
      <p>Please enter your Aadhaar number to begin verification.</p>
      
      <div className="registration-layout">
        <div className="webcam-container">
          <h3>Live Camera Feed</h3>
          <Webcam audio={false} ref={webcamRef} screenshotFormat="image/jpeg" width={480} height={360} />
        </div>
        
        <form onSubmit={handleVerifyAndRegister} className="form-container">
          <h3>Register Your Details</h3>
          
          <fieldset disabled={showOtpInput}>
            <input type="text" value={aadhaarNumber} onChange={(e) => setAadhaarNumber(e.target.value)} placeholder="Enter 12-digit Aadhaar number" required />
          </fieldset>

          {!showOtpInput ? (
            <button type="button" className="button-primary" onClick={handleSendOtp}>Verify Aadhaar & Send OTP</button>
          ) : (
            <>
              <hr />
              <h4>Welcome, {userName}!</h4>
              <p>Please enter the 6-digit code from the **Flask terminal** and capture your face.</p>
              <input type="text" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Enter 6-digit OTP" required />
              <button type="submit" className="button-primary">Verify & Register Face</button>
            </>
          )}
        </form>
      </div>
    </div>
  );

  const renderLoginView = () => ( /* ... (this code is unchanged) ... */
    <div className="page-container">
      <h2>Voter Authentication</h2>
      <p>Please use your face to log in and cast your vote.</p>
      <div className="webcam-container" style={{alignItems: 'center'}}>
        <h3>Login with Your Face</h3>
<p className="instruction">
  Please blink once and move your head left and right
</p>

        <Webcam audio={false} ref={webcamRef} screenshotFormat="image/jpeg" width={480} height={360} />
        <button className="button-primary login-button" onClick={handleLogin}>Authenticate</button>
      </div>
    </div>
  );
  
  const renderVoteBallotView = () => ( /* ... (this code is unchanged) ... */
    <div className="page-container voting-container">
      <h2>Welcome, {loggedInVoter.voterName}!</h2>
      <p>Please cast your vote for the position of Class Representative.</p>
      <div className="candidates">
          <div className="candidate-card" onClick={() => handleVote('Candidate A')}>
              <h3>Candidate A</h3>
              <p>Party of Unity</p>
          </div>
          <div className="candidate-card" onClick={() => handleVote('Candidate B')}>
              <h3>Candidate B</h3>
              <p>Party of Progress</p>
          </div>
          <div className="candidate-card" onClick={() => handleVote('Candidate C')}>
              <h3>Candidate C</h3>
              <p>Party of Innovation</p>
          </div>
      </div>
    </div>
  );
  
  const renderCandidatesView = () => ( /* ... (this code is unchanged) ... */
    <div className="page-container">
      <h2>Meet the Candidates</h2>
      <p>Here are the official (fictional) candidates for the project election.</p>
      <div className="candidates" style={{marginTop: '20px'}}>
        <div className="candidate-card static">
            <h3>Candidate A</h3>
            <p>Party of Unity</p>
            <p className="candidate-bio">"I believe in working together to build a stronger campus community."</p>
        </div>
        <div className="candidate-card static">
            <h3>Candidate B</h3>
            <p>Party of Progress</p>
            <p className="candidate-bio">"My focus is on modernization, technology, and future-ready skills."</p>
        </div>
        <div className="candidate-card static">
            <h3>Candidate C</h3>
            <p>Party of Innovation</p>
            <p className="candidate-bio">"Let's bring new ideas to the table and solve old problems."</p>
        </div>
      </div>
    </div>
  );
  
  const renderContactView = () => ( /* ... (this code is unchanged) ... */
    <div className="page-container contact-page">
      <h2>Contact Us</h2>
      <p>Have questions or need assistance with the voting process?</p>
      <p>Please reach out to the election committee.</p>
      <div className="contact-info">
        <p><strong>Email:</strong> support@svuce-voting.edu</p>
        <p><strong>Phone:</strong> +91-0877-22XXXXX</p>
        <p><strong>Office:</strong> Room 102, Admin Building, SVU College of Engineering, Tirupati</p>
      </div>
    </div>
  );

  // --- Main Render Method (Unchanged) ---
  return (
    <div className="App">
      <nav className="navbar">
        <div className="nav-brand">
          Secure E-Voting System
        </div>
        <div className="nav-links">
          <button className={`nav-button ${view === 'home' ? 'active' : ''}`} onClick={() => changeView('home')}>Home</button>
          <button className={`nav-button ${view === 'register' ? 'active' : ''}`} onClick={() => changeView('register')}>Register</button>
          <button className={`nav-button ${view === 'login' ? 'active' : ''}`} onClick={() => changeView('login')}>Login</button>
          <button className={`nav-button ${view === 'candidates' ? 'active' : ''}`} onClick={() => changeView('candidates')}>Candidates</button>
          <button className={`nav-button ${view === 'contact' ? 'active' : ''}`} onClick={() => changeView('contact')}>Contact Us</button>
        </div>
      </nav>

      <main className="main-content">
        {message.text && (
          <div className={`message ${message.type}`}>
            {message.text}
          </div>
        )}
        {view === 'home' && renderHomeView()}
        {view === 'register' && renderRegisterView()}
        {view === 'login' && renderLoginView()}
        {view === 'voting' && renderVoteBallotView()}
        {view === 'candidates' && renderCandidatesView()}
        {view === 'contact' && renderContactView()}
      </main>

      <footer className="footer">
        <p>&copy; 2025 SVU College of Engineering, Tirupati, Andhra Pradesh. Final Year Project.</p>
      </footer>
    </div>
  );
}

export default App;
