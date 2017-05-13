from pyplanet.apps.config import AppConfig
from pyplanet.apps.contrib.live_rankings.views import LiveRankingsWidget
from pyplanet.contrib.command import Command

from pyplanet.apps.core.trackmania import callbacks as tm_signals
from pyplanet.apps.core.maniaplanet import callbacks as mp_signals

from pyplanet.utils import times


class LiveRankings(AppConfig):
	game_dependencies = ['trackmania']
	app_dependencies = ['core.maniaplanet', 'core.trackmania']

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.current_rankings = []
		self.widget = None

	async def on_start(self):
		# Register signals
		self.instance.signal_manager.listen(mp_signals.map.map_begin, self.map_begin)
		self.instance.signal_manager.listen(tm_signals.finish, self.player_finish)
		self.instance.signal_manager.listen(tm_signals.waypoint, self.player_waypoint)
		self.instance.signal_manager.listen(mp_signals.player.player_connect, self.player_connect)
		self.instance.signal_manager.listen(tm_signals.scores, self.scores)

		self.widget = LiveRankingsWidget(self)
		await self.widget.display()

		scores = await self.instance.gbx.script('Trackmania.GetScores')
		await self.handle_scores(scores['players'])
		await self.widget.display()

	async def scores(self, section, players, **kwargs):
		await self.handle_scores(players)
		await self.widget.display()

	async def handle_scores(self, players):
		current_script = await self.instance.mode_manager.get_current_script()
		if 'TimeAttack' in current_script:
			self.current_rankings = []
			for player in players:
				if 'best_race_time' in player:
					if player['best_race_time'] != -1:
						new_ranking = dict(nickname=player['player'].nickname, score=player['best_race_time'])
						self.current_rankings.append(new_ranking)
				elif 'bestracetime' in player:
					if player['bestracetime'] != -1:
						new_ranking = dict(nickname=player['name'], score=player['bestracetime'])
						self.current_rankings.append(new_ranking)

				self.current_rankings.sort(key=lambda x: x['score'])
				self.widget.format_times = True
		elif 'Rounds' in current_script or 'Team' in current_script:
			self.current_rankings = []
			for player in players:
				if 'map_points' in player:
					if player['map_points'] != -1:
						new_ranking = dict(nickname=player['player'].nickname, score=player['map_points'])
						self.current_rankings.append(new_ranking)
				elif 'mappoints' in player:
					if player['mappoints'] != -1:
						new_ranking = dict(nickname=player['name'], score=player['mappoints'])
						self.current_rankings.append(new_ranking)

				self.current_rankings.sort(key=lambda x: x['score'])
				self.current_rankings.reverse()
				self.widget.format_times = False
		else:
			self.current_rankings = []
			print(players)

	async def map_begin(self, map):
		self.current_rankings = []
		await self.widget.display()

	async def player_connect(self, player, is_spectator, source, signal):
		await self.widget.display(player=player)

	async def player_waypoint(self, player, race_time, flow, raw):
		if 'Laps' not in await self.instance.mode_manager.get_current_script():
			return

		print("waypoint", raw)
		await self.widget.display(player=player)

	async def player_finish(self, player, race_time, lap_time, cps, flow, raw, **kwargs):
		if 'TimeAttack' not in await self.instance.mode_manager.get_current_script():
			return

		current_rankings = [x for x in self.current_rankings if x['nickname'] == player.nickname]
		score = lap_time
		if len(current_rankings) > 0:
			current_ranking = current_rankings[0]

			if score < current_ranking['score']:
				current_ranking['score'] = score
				self.current_rankings.sort(key=lambda x: x['score'])
				await self.widget.display()
		else:
			new_ranking = dict(nickname=player.nickname, score=score)
			self.current_rankings.append(new_ranking)
			self.current_rankings.sort(key=lambda x: x['score'])
			await self.widget.display()
