import { useEffect, useState } from 'react';
import Routes from '../configuration/routes/RouteList';
import { useNavigate } from 'react-router-dom';
import Colours from '../configuration/colours/Colours';
import Button from '../components/Button';
import signIn from '../api/actions/signIn';
import loadAuth from '../api/loader/loadAuth';
import LoadingIndicator from '../components/LoadingIndicator';

const Login = () => {
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [saveLogin, setSaveLogin] = useState(false);
  const [waitingForBackend, setWaitingForBackend] = useState(false);
  const [waitedCount, setWaitedCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: { preventDefault: () => void }) => {
    event.preventDefault();

    if (waitingForBackend) {
      return false;
    }

    setErrorMessage(null);

    const loginResponse = await signIn(username, password, saveLogin);

    const signedIn = loginResponse.status === 204;

    if (signedIn) {
      navigate(Routes.Home);
    } else {
      const data = await loginResponse.json();
      setErrorMessage(data?.error || 'Unknown Error');
      navigate(Routes.Login);
    }
  };

  useEffect(() => {
    let retryCount = 0;
    const startTime = Date.now();

    console.log('🚀 [Backend Check] Starting backend connection monitoring...');

    const backendCheckInterval = setInterval(async () => {
      const attemptTime = Date.now();
      const elapsedSeconds = Math.round((attemptTime - startTime) / 1000);
      
      console.log(`⏳ [Backend Check] Attempt #${retryCount + 1} (${elapsedSeconds}s elapsed)`);
      
      try {
        const auth = await loadAuth();
        const responseTime = Date.now() - attemptTime;
        
        console.log(`📡 [Backend Check] Response received (${responseTime}ms):`, {
          status: auth.status,
          statusText: auth.statusText,
          ok: auth.ok,
          url: auth.url,
          headers: {
            'content-type': auth.headers.get('content-type'),
            'set-cookie': auth.headers.get('set-cookie') ? '[present]' : '[none]'
          }
        });

        let authData;
        try {
          authData = await auth.json();
          console.log('📄 [Backend Check] Response data parsed:', authData);
        } catch (parseError) {
          console.error('❌ [Backend Check] Failed to parse JSON response:', parseError);
          console.log('📝 [Backend Check] Raw response body (first 500 chars):', await auth.text().then(t => t.substring(0, 500)));
          throw new Error(`JSON parse failed: ${parseError instanceof Error ? parseError.message : String(parseError)}`);
        }

        if (auth.status === 403) {
          console.log('🔒 [Backend Check] Authentication required (403) - Backend ready, showing login form');
          console.log('✅ [Backend Check] SUCCESS: Backend is accessible, stopping connection checks');
          setWaitingForBackend(false);
          clearInterval(backendCheckInterval);
          return;
        }

        if (authData.response === 'pong') {
          console.log('🎯 [Backend Check] Received pong response - User already authenticated');
          console.log('✅ [Backend Check] SUCCESS: Redirecting to home page');
          setWaitingForBackend(false);
          clearInterval(backendCheckInterval);
          navigate(Routes.Home);
          return;
        }

        // Unexpected success case
        console.warn('⚠️ [Backend Check] Unexpected response:', {
          status: auth.status,
          data: authData,
          willContinueChecking: true
        });
        
      } catch (error) {
        const responseTime = Date.now() - attemptTime;
        retryCount += 1;
        
        // Detailed error logging
        const errorInfo = {
          message: error instanceof Error ? error.message : String(error),
          name: error instanceof Error ? error.name : typeof error,
          stack: error instanceof Error ? error.stack : undefined,
          attemptNumber: retryCount,
          responseTime: `${responseTime}ms`,
          elapsedTime: `${elapsedSeconds}s`,
          errorType: 'EXCEPTION_CAUGHT'
        };
        
        console.error(`❌ [Backend Check] Exception caught - TRIGGERING "waiting for backend":`, errorInfo);
        
        // Specific error type analysis
        if (error instanceof TypeError && error.message.includes('fetch')) {
          console.error('🌐 [Backend Check] Network/Fetch error detected - likely connection issue');
        } else if (error instanceof Error && error.name === 'AbortError') {
          console.error('⏰ [Backend Check] Request timeout detected');
        } else if (error instanceof Error && error.message.includes('CORS')) {
          console.error('🚫 [Backend Check] CORS error detected');
        } else if (error instanceof Error && error.message.includes('JSON')) {
          console.error('📋 [Backend Check] JSON parsing error - backend returned non-JSON response');
        } else {
          console.error('❓ [Backend Check] Unknown error type');
        }
        
        console.log(`🔄 [Backend Check] Setting waitingForBackend=true, retryCount=${retryCount}`);
        setWaitedCount(retryCount);
        setWaitingForBackend(true);
        
        if (retryCount === 1) {
          console.log('ℹ️ [Backend Check] First failure - this is normal during startup');
        } else if (retryCount === 5) {
          console.warn('⚠️ [Backend Check] 5 failures - backend may be starting up or misconfigured');
        } else if (retryCount === 10) {
          console.warn('🔧 [Backend Check] 10 failures - "Having issues?" UI will appear on next failure');
        } else if (retryCount > 10) {
          console.warn(`🆘 ${retryCount} failures - "Having issues?" UI should be visible`);
        }
      }
    }, 1000);

    return () => {
      clearInterval(backendCheckInterval);
    };
  }, [navigate]);

  return (
    <>
      <title>TA | Welcome</title>
      <Colours />
      <div className="boxed-content login-page">
        <img alt="tube-archivist-logo" />
        <h1>Tube Archivist</h1>
        <h2>Your Self Hosted YouTube Media Server</h2>

        {errorMessage !== null && (
          <p className="danger-zone">
            Failed to login.
            <br />
            {errorMessage}
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            name="username"
            id="id_username"
            placeholder="Username"
            autoComplete="username"
            maxLength={150}
            required={true}
            value={username}
            onChange={event => setUsername(event.target.value)}
          />

          <br />

          <input
            type="password"
            name="password"
            id="id_password"
            placeholder="Password"
            autoComplete="current-password"
            required={true}
            value={password}
            onChange={event => setPassword(event.target.value)}
          />

          <br />

          <p>
            Remember me:{' '}
            <input
              type="checkbox"
              name="remember_me"
              id="id_remember_me"
              checked={saveLogin}
              onChange={() => {
                setSaveLogin(!saveLogin);
              }}
            />
          </p>

          <input type="hidden" name="next" value={Routes.Home} />

          {waitingForBackend && (
            <>
              <p>
                Waiting for backend <LoadingIndicator />
              </p>
            </>
          )}

          {!waitingForBackend && <Button label="Login" type="submit" />}
        </form>

        {waitedCount > 10 && (
          <div className="info-box">
            <div className="info-box-item">
              <h2>Having issues?</h2>

              <div className="help-text left-align">
                <p>Please verify that you setup your environment correctly:</p>
                <ul>
                  <li
                    onClick={() => {
                      navigator.clipboard.writeText(`TA_HOST=${window.location.origin}`);
                    }}
                  >
                    TA_HOST={window.location.origin}
                  </li>
                  <li
                    onClick={() => {
                      navigator.clipboard.writeText('REDIS_CON=redis://archivist-redis:6379');
                    }}
                  >
                    REDIS_CON=redis://archivist-redis:6379
                  </li>
                </ul>
              </div>
            </div>
          </div>
        )}

        <p className="login-links">
          <span>
            <a href="https://github.com/tubearchivist/tubearchivist" target="_blank">
              Github
            </a>
          </span>{' '}
          <span>
            <a href="https://github.com/tubearchivist/tubearchivist#donate" target="_blank">
              Donate
            </a>
          </span>
        </p>
      </div>
      <div className="footer-colors">
        <div className="col-1"></div>
        <div className="col-2"></div>
        <div className="col-3"></div>
      </div>
    </>
  );
};

export default Login;
