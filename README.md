# Home Assistant Dashboard Plugin

A custom Home Assistant dashboard plugin that can be installed through HACS.

## Installation

1. Make sure you have [HACS](https://hacs.xyz) installed in your Home Assistant instance
2. Add this repository to HACS as a custom repository:
   - Click on HACS in the sidebar
   - Click on the three dots in the top right corner
   - Click on "Custom repositories"
   - Add the URL of this repository
   - Select "Integration" as the category

3. Install the integration through HACS
4. Restart Home Assistant

## Configuration

1. Go to Configuration > Integrations
2. Click the "+ ADD INTEGRATION" button
3. Search for "Home Assistant Dashboard"
4. Follow the configuration steps

## Docker Compose Setup

Add this to your Home Assistant docker-compose.yml:

```yaml
version: '3'
services:
  homeassistant:
    image: homeassistant/home-assistant:stable
    volumes:
      - ./config:/config
      - ./custom_components:/config/custom_components
      - ./share:/share  # For storing generated images
    environment:
      - TZ=YOUR_TIME_ZONE
    restart: unless-stopped
```

## Usage

[Add usage instructions here]

## Development

[Add development instructions here]

## License

MIT License - see the [LICENSE](LICENSE) file for details