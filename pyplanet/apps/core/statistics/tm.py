"""
Trackmania app component.
"""
import logging
import datetime
from peewee import fn

from pyplanet.apps.core.maniaplanet.models import Player
from pyplanet.apps.core.statistics.models import Score, Rank
from pyplanet.apps.core.statistics.views.dashboard import StatsDashboardView
from pyplanet.apps.core.statistics.views.ranks import TopRanksView
from pyplanet.apps.core.statistics.views.records import TopSumsView
from pyplanet.apps.core.statistics.views.score import StatsScoresListView
from pyplanet.apps.core.trackmania.callbacks import finish
from pyplanet.apps.core.maniaplanet.callbacks import map
from pyplanet.contrib.command import Command
from pyplanet.contrib.setting import Setting

from pyplanet.apps.contrib.local_records import LocalRecord

logger = logging.getLogger(__name__)


class TrackmaniaComponent:
	def __init__(self, app):
		"""
		Initiate trackmania statistics component.

		:param app: App config instance
		:type app: pyplanet.apps.core.statistics.Statistics
		"""
		self.app = app

		self.setting_records_required = Setting(
			'minimum_records_required', 'Minimum of records required to acquire a rank.', Setting.CAT_BEHAVIOUR, type=int,
			description='Minimum of records required to acquire a rank (minimum 3 records).',
			default=5
		)

	async def on_init(self):
		pass

	async def on_start(self):
		# Listen to signals.
		self.app.context.signals.listen(finish, self.on_finish)
		self.app.context.signals.listen(map.map_end, self.on_map_end)

		# Register commands.
		await self.app.instance.command_manager.register(
			# Command('stats', target=self.open_stats),
			Command('topsums', target=self.topsums, description='Displays a list of top record players.'),
			Command('topranks', target=self.topranks, description='Displays a list of top ranked players.'),
			Command(command='scoreprogression', aliases=['progression'], target=self.open_score_progression,
					description='Displays your time/score progression on the current map.'),
		)

		# Register settings
		await self.app.context.setting.register(self.setting_records_required)

	async def on_finish(self, player, race_time, lap_time, cps, flow, raw, **kwargs):
		# Register the score of the player.
		await Score(
			player=player,
			map=self.app.instance.map_manager.current_map,
			score=race_time,
			checkpoints=','.join([str(cp) for cp in cps])
		).save()

	async def on_map_end(self, map):
		# Calculate server ranks.
		await self.calculate_server_ranks()

	async def calculate_server_ranks(self):
		# Save calculation start time.
		start_time = datetime.datetime.now()

		# Truncate the ranking table.
		await Rank.execute(Rank.delete())

		# Rankings depend on the local records.
		if 'local_records' not in self.app.instance.apps.apps:
			return

		# Retrieve settings.
		# TODO: retrieve max rank from local records.
		minimum_records_required_setting = await self.setting_records_required.get_value()
		minimum_records_required = minimum_records_required_setting if minimum_records_required_setting >= 3 else 3
		maximum_record_rank = await self.app.instance.apps.apps['local_records'].setting_record_limit.get_value()

		# Retrieve all players eligible for a ranking (min. 3 records).
		eligible_players = await LocalRecord.execute(
			LocalRecord.select(LocalRecord.player, fn.Count(LocalRecord.id))
			.group_by(LocalRecord.player)
			.where(LocalRecord.map << [map_on_server.id for map_on_server in self.app.instance.map_manager.maps])
			.having(fn.Count(LocalRecord.id) > minimum_records_required))

		if len(eligible_players) == 0:
			return

		# Retrieve count of maps on server and initialize player record ranks array.
		server_map_count = len(self.app.instance.map_manager.maps)
		player_record_ranks = dict([(eligible_player.player_id, list()) for eligible_player in eligible_players])
		eligible_players_ids = [eligible_player.player_id for eligible_player in eligible_players]

		# Loop through all maps to determine the personal ranks on each map.
		for map_on_server in self.app.instance.map_manager.maps:
			map_records = list(await LocalRecord.execute(
				LocalRecord.select(LocalRecord.map, LocalRecord.player, LocalRecord.score)
					.where(LocalRecord.map_id == map_on_server.id)
					.order_by(LocalRecord.map_id.asc(), LocalRecord.score.asc())
			))

			for map_record in [eligible_record for eligible_record in map_records if (eligible_record.player_id in eligible_players_ids)]:
				map_player_rank = (map_records.index(map_record) + 1)
				if map_player_rank <= maximum_record_rank:
					player_record_ranks[map_record.player_id].append(map_player_rank)

		calculated_ranks = []

		# Determine ranking average and submit rankings to the database.
		for player_id in player_record_ranks:
			player_ranked_records = len(player_record_ranks[player_id])
			player_average_rank = (sum(player_record_ranks[player_id]) + ((server_map_count - player_ranked_records) * maximum_record_rank)) / server_map_count
			player_average_rank = round(player_average_rank * 10000)

			calculated_ranks.append({
				'player': player_id,
				'average': player_average_rank
			})

		await Rank.objects.execute(Rank.insert_many(calculated_ranks))

		logger.info('[RANKING] Total time elapsed: {}ms'.format((datetime.datetime.now() - start_time).total_seconds() * 1000))

	async def open_stats(self, player, **kwargs):
		view = StatsDashboardView(self.app, self.app.context.ui, player)
		await view.display()

	async def open_score_progression(self, player, **kwargs):
		view = StatsScoresListView(self.app, player)
		await view.display(player)

	async def topsums(self, player, *args, **kwargs):
		await self.app.instance.chat('$0f3Loading Top Record Players ...', player)
		view = TopSumsView(self.app, player, await self.app.processor.get_topsums())
		await view.display(player)

	async def topranks(self, player, *args, **kwargs):
		top_ranks = await Rank.objects.execute(Rank.select(Rank, Player).join(Player).order_by(Rank.average.asc()).limit(100))
		view = TopRanksView(self.app, player, top_ranks)
		await view.display(player)
