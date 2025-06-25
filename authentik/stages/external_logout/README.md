# External Logout Stage

The External Logout Stage provides a way to notify external systems when a user logs out from Authentik. This stage can handle both single application logout and global logout scenarios by making HTTP requests to external logout endpoints.

## Features

- **Single Application Logout**: Logout from a specific application
- **Global Logout**: Logout from all applications with active OAuth2 tokens
- **Configurable HTTP Requests**: Support for GET, POST, and DELETE methods
- **Template Support**: Dynamic URL and request body templating with user/session data
- **Token Revocation**: Automatic OAuth2 token revocation
- **Error Handling**: Configurable error handling behavior
- **Timeout Control**: Configurable request timeouts

## Configuration

### Basic Settings

- **Name**: A descriptive name for the stage
- **Logout URL Template**: URL template for the external logout endpoint
- **HTTP Method**: HTTP method to use (GET, POST, DELETE)
- **Request Timeout**: Timeout in seconds for HTTP requests (1-300 seconds)

### Advanced Settings

- **Request Body Template**: Template for request body (used with POST requests)
- **Additional Headers**: JSON object with additional HTTP headers
- **Global Logout**: Enable to logout from all connected applications
- **Revoke OAuth Tokens**: Whether to revoke OAuth2 tokens during logout
- **Ignore Errors**: Whether to continue the logout flow if external requests fail

## Template Placeholders

The following placeholders are available in URL and request body templates:

- `{user_id}`: The user's database ID
- `{username}`: The user's username
- `{email}`: The user's email address
- `{session_id}`: The current session ID
- `{client_id}`: The OAuth2 client ID (when available)

## Usage Examples

### Single Application Logout

Configure the stage with:
- **Global Logout**: Disabled
- **Logout URL Template**: `https://app.example.com/logout?user={username}&session={session_id}`
- **HTTP Method**: POST
- **Request Body Template**: `{"username": "{username}", "logout_type": "single"}`

### Global Logout from All Applications

Configure the stage with:
- **Global Logout**: Enabled
- **Logout URL Template**: `https://app.example.com/logout`
- **HTTP Method**: POST
- **Request Body Template**: `{"username": "{username}", "logout_type": "global", "client_id": "{client_id}"}`

### OIDC Logout Endpoint

For OIDC-compliant logout:
- **Logout URL Template**: `https://app.example.com/oidc/logout?id_token_hint={session_id}&post_logout_redirect_uri=https://sso.example.com/logged-out`
- **HTTP Method**: GET

## Flow Integration

### End Session Flow

1. Create a new flow with designation "Invalidation"
2. Add the External Logout Stage to the flow
3. Configure your OAuth2 provider to use this flow as the "Invalidation Flow"
4. Users accessing `/application/o/your-app/end-session/` will trigger this flow

### Manual Logout Flow

1. Create a logout button/link in your application
2. Redirect users to the end-session URL: `https://your-authentik.domain/application/o/your-app/end-session/`
3. The External Logout Stage will handle notifying external systems

## Implementation Details

### Single Application Mode

When `global_logout` is `False`:
1. Gets the current application from the flow context
2. Makes an HTTP request to the configured logout endpoint
3. Revokes tokens for the current application (if enabled)
4. Logs out the user from Authentik

### Global Logout Mode

When `global_logout` is `True`:
1. Finds all applications with active OAuth2 tokens for the user
2. Makes HTTP requests to each application's logout endpoint
3. Revokes all OAuth2 tokens for the user (if enabled)
4. Logs out the user from Authentik

### Error Handling

- **Ignore Errors = True**: HTTP errors are logged but don't prevent logout
- **Ignore Errors = False**: HTTP errors are logged and may affect the flow
- Network timeouts and connection errors are always logged

## Security Considerations

- Always use HTTPS for logout URLs in production
- Validate SSL certificates (certificate verification is always enabled)
- Use secure headers and authentication if required by external systems
- Consider implementing rate limiting on external logout endpoints
- Regularly rotate any authentication tokens used in headers

## Troubleshooting

### Common Issues

1. **Template formatting errors**: Check that all placeholders are spelled correctly
2. **Timeout errors**: Increase the request timeout if external systems are slow
3. **SSL errors**: Ensure external systems have valid SSL certificates
4. **Authentication errors**: Verify additional headers contain correct authentication

### Logging

The stage logs all HTTP requests and responses. Check Authentik logs for:
- `External logout request successful`
- `External logout request failed`
- `External logout request timed out`

### Testing

Test the stage by:
1. Creating a test application with the External Logout Stage
2. Logging in to the application
3. Accessing the end-session URL
4. Checking both Authentik logs and external system logs

## API Integration

The stage is automatically registered with the Authentik API at:
- `GET /api/v3/stages/external_logout/` - List stages
- `POST /api/v3/stages/external_logout/` - Create stage
- `GET /api/v3/stages/external_logout/{uuid}/` - Get stage
- `PUT /api/v3/stages/external_logout/{uuid}/` - Update stage
- `DELETE /api/v3/stages/external_logout/{uuid}/` - Delete stage