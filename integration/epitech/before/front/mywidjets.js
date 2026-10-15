import Clockwidget from './Clockwidget'
import WheaterWidget from './WheaterWidget'
import ForecastWidget from './ForecastWidget'
import NasaWidget from './widgetNasa'
import GithubWidget from './Github'
import GithubCommits from './GithubCommits'
import Steam from './SteamWidget'
import RssWidget from './RssWidget'

// One entry per widget of backend/services/registry.py (what /about.json
// lists). `service` / `widget` are its names there, used to save the
// dashboard (see hooks/useWidjets.js). `fields` are the widget's
// configurable params, edited in WidgetSettings; `defaultConfig` is used when
// the widget is first added. `requires` names the account the user must have
// linked in their profile to see the widget.
// The "weather" and "forecast" widgets also get a city search in
// WidgetSettings, which fills `city`, `latitude` and `longitude`.
export const WIDGET_REGISTRY = {
  clock: {
    component: Clockwidget,
    label: 'Horloge',
    service: 'time',
    widget: 'clock',
    defaultSize: { w: 2, h: 2 },
    defaultConfig: { timezone: 'Indian/Reunion' },
    fields: [],
  },

  weather: {
    component: WheaterWidget,
    label: 'Météo',
    service: 'weather',
    widget: 'city_temperature',
    defaultSize: { w: 2, h: 2 },
    defaultConfig: {},
    fields: [],
  },

  forecast: {
    component: ForecastWidget,
    label: 'Prévisions',
    service: 'weather',
    widget: 'city_forecast',
    defaultSize: { w: 3, h: 2 },
    defaultConfig: { days: 5 },
    fields: [
      { key: 'days', label: 'Nombre de jours (1 à 16)', type: 'number', min: 1, max: 16 },
    ],
  },

  nasa: {
    component: NasaWidget,
    label: 'NASA',
    service: 'nasa_picture',
    widget: 'daily_picture',
    defaultSize: { w: 3, h: 3 },
    defaultConfig: { days_ago: 0 },
    fields: [
      { key: 'days_ago', label: 'Image d’il y a combien de jours (0 = aujourd’hui)', type: 'number', min: 0 },
    ],
  },

  github: {
    component: GithubWidget,
    label: 'GitHub',
    service: 'github',
    widget: 'user_profile',
    requires: 'github',
    defaultSize: { w: 4, h: 4 },
    // The profile of the GitHub account linked by the user
    defaultConfig: (githubLogin) => ({ username: githubLogin }),
    fields: [
      { key: 'username', label: 'Nom d’utilisateur GitHub', type: 'text', placeholder: 'octocat' },
    ],
  },

  github_commits: {
    component: GithubCommits,
    label: 'Commits GitHub',
    service: 'github',
    widget: 'recent_commits',
    requires: 'github',
    defaultSize: { w: 3, h: 3 },
    // One of the user's own repositories: only the name is left to fill in
    defaultConfig: (githubLogin) => ({ owner: githubLogin, repo: '' }),
    fields: [
      { key: 'owner', label: 'Propriétaire du dépôt', type: 'text', placeholder: 'facebook' },
      { key: 'repo', label: 'Nom du dépôt', type: 'text', placeholder: 'react' },
    ],
  },

  rss: {
    component: RssWidget,
    label: 'Flux RSS',
    service: 'rss',
    widget: 'article_list',
    defaultSize: { w: 3, h: 3 },
    defaultConfig: { link: 'https://www.lemonde.fr/rss/une.xml', number: 5 },
    fields: [
      { key: 'link', label: 'Adresse du flux RSS', type: 'url', placeholder: 'https://www.lemonde.fr/rss/une.xml' },
      { key: 'number', label: 'Nombre d’articles (1 à 20)', type: 'number', min: 1, max: 20 },
    ],
  },

  steam: {
    component: Steam,
    label: 'Steam',
    service: 'steam',
    widget: 'global_achievements',
    defaultSize: { w: 3, h: 3 },
    defaultConfig: { game_id: 440 },
    fields: [
      { key: 'game_id', label: 'ID du jeu Steam (ex : 440, 730)', type: 'number', min: 1 },
    ],
  },
}
