import { Module } from '@nestjs/common';
import { WatchlistController } from './watchlist.controller';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  controllers: [WatchlistController],
})
export class WatchlistModule {}